# api/app/faiss_index.py
"""
FAISS 기반 벡터 검색 엔진
E5 임베딩 모델 + FAISS IndexFlatIP 사용
"""

import faiss
import numpy as np
import pickle
import os
from typing import List, Union, Any, Tuple
from dataclasses import dataclass
from .doc_chunker import Chunk
from .cache_manager import pdf_cache_manager

@dataclass
class SearchResult:
    chunk: Chunk
    score: float
    citation: str

class FaissIndex:
    """FAISS 기반 벡터 검색 인덱스"""
    
    def __init__(self, embedding_model: Union[str, Any] = "intfloat/multilingual-e5-base"):
        """
        Args:
            embedding_model: 모델명(str) 또는 모델 객체
                - str: HuggingFace SentenceTransformer 모델명
                - object: 이미 로드된 임베딩 모델 객체
        """
        self.embedding_model = self._load_embedding_model(embedding_model)
        self.index = None
        self.chunks = []
        self.embedding_dim = None
        
    def _load_embedding_model(self, model_input: Union[str, Any]) -> Any:
        """임베딩 모델 로드"""
        if isinstance(model_input, str):
            # HuggingFace 모델명인 경우
            try:
                from sentence_transformers import SentenceTransformer
                print(f"🤖 Loading embedding model: {model_input}")
                model = SentenceTransformer(model_input)
                print(f"✅ Model loaded successfully")
                return model
            except Exception as e:
                print(f"❌ Failed to load model {model_input}: {e}")
                # Fallback to smaller model
                print("🔄 Falling back to smaller model: all-MiniLM-L6-v2")
                return SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        else:
            # 이미 로드된 모델 객체인 경우
            print(f"✅ Using provided embedding model: {type(model_input)}")
            return model_input
    
    def _get_embedding_with_instruction(self, text: str, is_query: bool = False) -> np.ndarray:
        """E5 모델의 instruction prefix 적용"""
        if "e5" in str(type(self.embedding_model)).lower() or "e5" in getattr(self.embedding_model, 'model_name', '').lower():
            # E5 모델인 경우 instruction prefix 적용
            if is_query:
                prefixed_text = f"query: {text}"
            else:
                prefixed_text = f"passage: {text}"
        else:
            # 다른 모델인 경우 그대로 사용
            prefixed_text = text
        
        embedding = self.embedding_model.encode(prefixed_text)
        return np.array(embedding, dtype=np.float32)
    
    def build_from_chunks(self, chunks: List[Chunk], filename: str = None) -> bool:
        """
        Chunk 리스트로부터 FAISS 인덱스 구축
        
        Args:
            chunks: doc_chunker에서 생성된 Chunk 객체들
            filename: 캐시 저장용 파일명
            
        Returns:
            bool: 구축 성공 여부
        """
        try:
            if not chunks:
                print("❌ No chunks provided for indexing")
                return False
            
            print(f"🔍 Building FAISS index from {len(chunks)} chunks")
            self.chunks = chunks
            
            # 임베딩 생성
            embeddings = []
            for i, chunk in enumerate(chunks):
                if not chunk.content.strip():
                    continue
                
                embedding = self._get_embedding_with_instruction(chunk.content, is_query=False)
                embeddings.append(embedding)
                
                if (i + 1) % 10 == 0:
                    print(f"📦 Processed {i + 1}/{len(chunks)} chunks")
            
            if not embeddings:
                print("❌ No valid embeddings generated")
                return False
            
            # 임베딩 배열 생성
            embedding_matrix = np.array(embeddings, dtype=np.float32)
            self.embedding_dim = embedding_matrix.shape[1]
            
            print(f"📐 Embedding dimension: {self.embedding_dim}")
            
            # FAISS 인덱스 생성 (내적 기반 - 코사인 유사도용)
            self.index = faiss.IndexFlatIP(self.embedding_dim)
            
            # L2 정규화 (내적을 코사인 유사도로 변환)
            faiss.normalize_L2(embedding_matrix)
            
            # 인덱스에 추가
            self.index.add(embedding_matrix)
            
            print(f"✅ FAISS index built successfully: {self.index.ntotal} vectors")
            
            # 캐시 저장
            if filename:
                self.save_to_cache(filename)
            
            return True
            
        except Exception as e:
            print(f"❌ Error building FAISS index: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """
        쿼리로 유사한 청크 검색
        
        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 수
            
        Returns:
            List[SearchResult]: 검색 결과 (유사도 내림차순)
        """
        try:
            if self.index is None or not self.chunks:
                print("❌ Index not built or no chunks available")
                return []
            
            # 쿼리 임베딩 생성
            query_embedding = self._get_embedding_with_instruction(query, is_query=True)
            query_vector = np.array([query_embedding], dtype=np.float32)
            
            # L2 정규화
            faiss.normalize_L2(query_vector)
            
            # 검색 실행
            scores, indices = self.index.search(query_vector, min(top_k, len(self.chunks)))
            
            # 결과 변환
            results = []
            for rank, (score, idx) in enumerate(zip(scores[0], indices[0])):
                if idx < len(self.chunks):
                    chunk = self.chunks[idx]
                    citation = f"[{rank + 1}] (Page {chunk.page_number})"
                    
                    result = SearchResult(
                        chunk=chunk,
                        score=float(score),
                        citation=citation
                    )
                    results.append(result)
            
            print(f"🎯 Found {len(results)} results for query: '{query[:50]}...'")
            return results
            
        except Exception as e:
            print(f"❌ Error searching: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def save_to_cache(self, filename: str) -> bool:
        """캐시에 인덱스 저장"""
        try:
            if self.index is None:
                return False
            
            cache_data = {
                'chunks': self.chunks,
                'embedding_dim': self.embedding_dim,
                'model_name': getattr(self.embedding_model, 'model_name', 'unknown'),
                'index_size': self.index.ntotal if self.index else 0
            }
            
            # 메타데이터 저장
            pdf_cache_manager.save(f"{filename}_faiss_meta", cache_data)
            
            # FAISS 인덱스 파일로 저장
            index_path = pdf_cache_manager.cache_dir / f"{filename}_faiss.index"
            faiss.write_index(self.index, str(index_path))
            
            print(f"💾 FAISS index cached: {filename}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving to cache: {e}")
            return False
    
    def load_from_cache(self, filename: str) -> bool:
        """캐시에서 인덱스 로드"""
        try:
            # 메타데이터 로드
            meta_data = pdf_cache_manager.load(f"{filename}_faiss_meta")
            if not meta_data:
                return False
            
            # FAISS 인덱스 파일 로드
            index_path = pdf_cache_manager.cache_dir / f"{filename}_faiss.index"
            if not index_path.exists():
                return False
            
            self.index = faiss.read_index(str(index_path))
            self.chunks = meta_data['chunks']
            self.embedding_dim = meta_data['embedding_dim']
            
            print(f"📂 FAISS index loaded from cache: {filename}")
            return True
            
        except Exception as e:
            print(f"❌ Error loading from cache: {e}")
            return False
    
    def get_stats(self) -> dict:
        """인덱스 통계 정보"""
        return {
            'total_vectors': self.index.ntotal if self.index else 0,
            'embedding_dim': self.embedding_dim,
            'total_chunks': len(self.chunks),
            'model_type': type(self.embedding_model).__name__,
            'is_trained': self.index is not None
        }


# 유틸리티 함수
def create_faiss_index_from_cache(filename: str, 
                                  model_name: str = "intfloat/multilingual-e5-base") -> FaissIndex:
    """
    캐시된 PDF에서 FAISS 인덱스 생성
    
    Args:
        filename: PDF 파일명
        model_name: 사용할 임베딩 모델명
        
    Returns:
        FaissIndex: 구축된 인덱스
    """
    from .doc_chunker import DocumentChunker
    
    # 기존 FAISS 캐시 확인
    faiss_index = FaissIndex(model_name)
    if faiss_index.load_from_cache(filename):
        print(f"✅ FAISS index loaded from cache: {filename}")
        return faiss_index
    
    # 캐시에서 청킹 수행
    try:
        chunker = DocumentChunker(chunking_method='cosine')
        chunks = chunker.chunk_document(filename)
        
        if chunks:
            success = faiss_index.build_from_chunks(chunks, filename)
            if success:
                print(f"✅ New FAISS index created: {filename}")
                return faiss_index
        
        print(f"❌ Failed to create FAISS index: {filename}")
        return None
        
    except Exception as e:
        print(f"❌ Error creating FAISS index: {e}")
        return None