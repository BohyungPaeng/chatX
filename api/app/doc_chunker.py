import re
import math
import numpy as np
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from collections import Counter

# 상수 정의 (참조 링크 기반)
SIMILARITY_THRESHOLD = 0.3  # 청크 분할 임계값
MIN_CHUNK_SIZE = 100        # 최소 청크 크기 (글자)
MAX_CHUNK_SIZE = 1000       # 최대 청크 크기 (글자)
SENTENCE_EMBEDDING_DIM = 384  # 문장 임베딩 차원 (사용하지 않음)

@dataclass
class Chunk:
    id: str                    # filename_page_chunk_순번
    content: str               # 청크 내용
    page_number: int           # 페이지 번호
    start_index: int           # 원본 텍스트 내 시작 위치 (문장 인덱스)
    end_index: int             # 원본 텍스트 내 종료 위치 (문장 인덱스)

class DocumentChunker:
    """
    참조 링크의 Adjacent Sentence Clustering 방식을 TF-IDF 기반 cosine similarity로 재현
    옵션으로 Jaccard similarity도 선택 가능
    """
    def __init__(self, similarity_metric: str = 'cosine'):
        """
        similarity_metric: 'cosine' 또는 'jaccard'
        """
        if similarity_metric not in ('cosine', 'jaccard'):
            raise ValueError("similarity_metric은 'cosine' 또는 'jaccard'이어야 합니다.")
        self.similarity_metric = similarity_metric

    def chunk_document(self, filename: str) -> List[Chunk]:
        """GLOBAL_PDF_CACHE에서 메타데이터를 가져와서 semantic chunking 수행"""
        from .routers import GLOBAL_PDF_CACHE
        
        cache_data = GLOBAL_PDF_CACHE.get(filename)
        if not cache_data:
            raise ValueError(f"PDF 메타데이터를 찾을 수 없습니다: {filename}")
        
        page_texts = cache_data.get('page_texts', [])
        all_chunks = []
        
        for page_text in page_texts:
            page_num, content = self._extract_page_content(page_text)
            if content.strip():
                page_chunks = self._chunk_page_semantically(content, page_num, filename)
                all_chunks.extend(page_chunks)
        
        return all_chunks
    
    def _extract_page_content(self, page_text: str) -> Tuple[int, str]:
        """'## 📄 페이지 X\n\n내용' 형식에서 페이지 번호와 내용 추출"""
        match = re.match(r'## 📄 페이지 (\d+)\n\n(.*)', page_text, re.DOTALL)
        if match:
            page_num = int(match.group(1))
            content = match.group(2).strip()
            return page_num, content
        return 1, page_text.strip()
    
    def _chunk_page_semantically(self, text: str, page_num: int, filename: str) -> List[Chunk]:
        """
        페이지별 텍스트를 semantic chunking으로 분할
        참조 링크의 Adjacent Sentence Clustering 방식 구현
        """
        
        # 1. 문장 단위로 분할
        sentences = self._split_into_sentences(text)
        if len(sentences) <= 1:
            return [self._create_chunk(text, page_num, filename, 0, 0)]
        
        # 2. 인접 문장 간 유사도 기반 클러스터링
        clusters = self._cluster_adjacent_sentences(sentences, SIMILARITY_THRESHOLD)
        
        # 3. 클러스터를 청크로 변환
        chunks = []
        for i, cluster_indices in enumerate(clusters):
            cluster_sentences = [sentences[idx] for idx in cluster_indices]
            chunk_text = ' '.join(cluster_sentences).strip()
            
            # 최소 크기 체크
            if len(chunk_text) >= MIN_CHUNK_SIZE:
                chunk_id = f"{filename}_page_{page_num}_chunk_{i+1}"
                chunk = Chunk(
                    id=chunk_id,
                    content=chunk_text,
                    page_number=page_num,
                    start_index=cluster_indices[0],
                    end_index=cluster_indices[-1]
                )
                chunks.append(chunk)
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        한글 문장 분할 (참조 링크의 접근 방식)
        """
        # 한글/영문 문장 부호 기준 분할
        sentence_endings = r'[.!?。！？]+\s*'
        sentences = re.split(sentence_endings, text)
        
        # 빈 문장 제거 및 정리
        clean_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and len(sentence) > 10:  # 너무 짧은 문장 제외
                clean_sentences.append(sentence)
        
        return clean_sentences
    
    def _cluster_adjacent_sentences(self, sentences: List[str], threshold: float) -> List[List[int]]:
        """
        참조 링크의 Adjacent Sentence Clustering 정확 재현
        연속된 문장 간 유사도를 계산하여 클러스터 생성
        """
        if len(sentences) <= 1:
            return [[0]] if sentences else []
        
        # 문장별 벡터 생성 (TF-IDF 기반)
        sentence_vectors = self._create_sentence_vectors(sentences)
        
        clusters = [[0]]  # 첫 번째 문장으로 시작
        current_cluster_start = 0
        
        for i in range(1, len(sentences)):
            if self.similarity_metric == 'cosine':
                similarity = self._calculate_cosine_similarity(
                    sentence_vectors[i-1], 
                    sentence_vectors[i]
                )
            else:
                similarity = self._calculate_jaccard_similarity(sentences[i-1], sentences[i])

            # 임계값보다 낮으면 새로운 클러스터 시작
            if similarity < threshold:
                clusters.append([])
                current_cluster_start = i
            
            # 현재 클러스터에 문장 추가
            clusters[-1].append(i)
            
            # 최대 크기 제한 체크
            current_chunk_text = ' '.join([sentences[idx] for idx in clusters[-1]])
            if len(current_chunk_text) > MAX_CHUNK_SIZE and len(clusters[-1]) > 1:
                # 현재 문장을 새 클러스터로 이동
                clusters[-1].pop()  # 현재 문장 제거
                clusters.append([i])  # 새 클러스터로 시작
        
        return clusters
    
    def _create_sentence_vectors(self, sentences: List[str]) -> List[np.ndarray]:
        """
        문장별 TF-IDF 벡터 생성 (벡터 임베딩 없이)
        참조 링크 방식을 단순화하여 구현
        """
        # 전체 어휘 구축
        all_words = set()
        sentence_words = []
        
        for sentence in sentences:
            words = self._tokenize_korean(sentence)
            sentence_words.append(words)
            all_words.update(words)
        
        vocab = list(all_words)
        vocab_size = len(vocab)
        word_to_idx = {word: idx for idx, word in enumerate(vocab)}
        
        # TF-IDF 벡터 계산
        vectors = []
        doc_freq = Counter()
        
        # 문서 빈도 계산
        for words in sentence_words:
            unique_words = set(words)
            for word in unique_words:
                doc_freq[word] += 1
        
        # 각 문장의 TF-IDF 벡터 생성
        for words in sentence_words:
            vector = np.zeros(vocab_size)
            word_count = Counter(words)
            
            for word, count in word_count.items():
                if word in word_to_idx:
                    idx = word_to_idx[word]
                    tf = count / len(words)  # Term Frequency
                    idf = math.log(len(sentences) / (doc_freq[word] + 1))  # Inverse Document Frequency
                    vector[idx] = tf * idf
            
            # 벡터 정규화
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = vector / norm
            
            vectors.append(vector)
        
        return vectors
    
    def _tokenize_korean(self, text: str) -> List[str]:
        """
        한글 토큰화 (간단한 공백 기반)
        외부 라이브러리 없이 구현
        """
        # 특수문자 제거 및 소문자 변환
        clean_text = re.sub(r'[^\w\s가-힣]', ' ', text)
        words = clean_text.lower().split()
        
        # 불용어 제거 (간단한 한글/영문 불용어)
        stopwords = {
            '이', '그', '저', '것', '수', '등', '및', '또는', '그리고', '하지만', '그러나',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'
        }
        
        filtered_words = [word for word in words if word not in stopwords and len(word) > 1]
        return filtered_words
    
    def _calculate_cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        두 벡터 간 코사인 유사도 계산
        참조 링크의 np.dot(vecs[i], vecs[i-1]) 방식 구현
        """
        # 이미 정규화된 벡터이므로 내적이 코사인 유사도
        similarity = np.dot(vec1, vec2)
        return float(similarity)
    
    def _calculate_jaccard_similarity(self, sent1: str, sent2: str) -> float:
        """
        두 문장 간 Jaccard 유사도 계산 (단어 집합 기반)
        """
        w1 = set(self._tokenize_korean(sent1))
        w2 = set(self._tokenize_korean(sent2))
        if not w1 or not w2:
            return 0.0
        inter = w1.intersection(w2)
        union = w1.union(w2)
        return len(inter) / len(union) if union else 0.0
    
    def _create_chunk(self, content: str, page_num: int, filename: str, start_idx: int) -> Chunk:
        """청크 객체 생성"""
        chunk_id = f"{filename}_page_{page_num}_chunk_1"
        return Chunk(
            id=chunk_id,
            content=content.strip(),
            page_number=page_num,
            start_index=start_idx,
            end_index=start_idx
        )
