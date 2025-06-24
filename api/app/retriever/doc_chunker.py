import re
import math
import numpy as np
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from collections import Counter

# 상수 정의
SIMILARITY_THRESHOLD = 0.3
MIN_CHUNK_SIZE = 20  # 완화됨 (semantic용)
MAX_CHUNK_SIZE = 1000

@dataclass
class Chunk:
    id: str
    content: str
    page_number: int  # 시작 페이지
    start_index: int = 0
    end_index: int = 0
    page_span: List[int] = None  # 걸쳐있는 모든 페이지들

    def __post_init__(self):
        if self.page_span is None:
            self.page_span = [self.page_number]

@dataclass
class ChunkDebugInfo:
    """청킹 디버깅 정보"""
    total_chunks: int
    page_distribution: Dict[int, int]
    size_distribution: Dict[str, int]
    empty_chunks: int
    duplicate_chunks: int
    similarity_scores: List[float]
    method_name: str

class DocumentChunker:
    """통합된 문서 청킹 클래스 - 전체 문서 기반"""
    
    def __init__(self, chunking_method: str = 'cosine'):
        """
        chunking_method: 'cosine', 'jaccard', 또는 'simple'
        """
        if chunking_method not in ('cosine', 'jaccard', 'simple'):
            raise ValueError("chunking_method는 'cosine', 'jaccard', 'simple' 중 하나여야 합니다.")
        self.chunking_method = chunking_method

    def chunk_document(self, cache_data_or_filename, filename: str = None) -> List[Chunk]:
        """
        전체 문서 통합 청킹 (페이지 경계 무시)
        """
        # 입력 타입 처리
        if isinstance(cache_data_or_filename, str):
            filename = cache_data_or_filename
            cache_data = self._get_cache_data(filename)
        else:
            cache_data = cache_data_or_filename
            if not filename:
                filename = cache_data.get('filename', 'unknown')
        
        page_texts = cache_data.get('page_texts', [])
        print(f"🔍 전체 문서 청킹 시작: {filename} ({len(page_texts)} 페이지)")
        
        # 🔥 전체 텍스트 통합 + 페이지 매핑
        full_text, page_mapping = self._merge_pages(page_texts)
        
        if self.chunking_method == 'simple':
            chunks = self._chunk_simple(full_text, page_mapping, filename)
        else:
            chunks = self._chunk_semantic(full_text, page_mapping, filename)
        
        print(f"✅ 전체 문서 청킹 완료: {len(chunks)}개 청크")
        return chunks
    

    
    def _merge_pages(self, page_texts: List[str]) -> Tuple[str, List[dict]]:
        """페이지들을 통합하면서 매핑 정보 유지"""
        full_text = ""
        page_mapping = []
        char_position = 0
        
        for page_text in page_texts:
            page_num, content = self._extract_page_content(page_text)
            
            if content.strip():
                start_pos = char_position
                full_text += content + "\n\n"
                char_position = len(full_text)
                end_pos = char_position
                
                page_mapping.append({
                    'page_num': page_num,
                    'start': start_pos,
                    'end': end_pos,
                    'content': content
                })
        
        return full_text, page_mapping
    
    def _chunk_simple(self, full_text: str, page_mapping: List[dict], filename: str) -> List[Chunk]:
        """간단한 길이 기반 청킹 (langchain RecursiveCharacterTextSplitter 스타일)"""
        from ..tools.langchain_chunker import RecursiveCharacterTextSplitter
        # 하이퍼파라미터
        chunk_size = 400  # 변경된 값
        chunk_overlap = 100  # 변경된 값
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ".", "!", "?", " ", ""]
        )
            
        text_chunks = splitter.split_text(full_text)
        print(f"📏 Simple 청킹: {len(text_chunks)}개 청크 (크기: {chunk_size}, 겹침: {chunk_overlap})")
            
        # 청크를 Chunk 객체로 변환
        chunks = []
        for i, chunk_text in enumerate(text_chunks):
            if chunk_text.strip():
                page_span = self._calculate_page_span(chunk_text, full_text, page_mapping)
                
                chunk = Chunk(
                    id=f"{filename}_simple_chunk_{i+1}",
                    content=chunk_text.strip(),
                    page_number=page_span[0] if page_span else 1,
                    page_span=page_span
                )
                chunks.append(chunk)
        
        return chunks
    
    def _chunk_semantic(self, full_text: str, page_mapping: List[dict], filename: str) -> List[Chunk]:
        """의미 기반 청킹 (cosine/jaccard)"""
        sentences = self._split_sentences(full_text)
        
        if len(sentences) <= 1:
            # 문장이 하나뿐이면 전체를 하나의 청크로
            page_span = [pm['page_num'] for pm in page_mapping]
            return [Chunk(
                id=f"{filename}_semantic_chunk_1",
                content=full_text.strip(),
                page_number=page_span[0] if page_span else 1,
                page_span=page_span
            )]
        
        clusters = self._cluster_sentences(sentences, SIMILARITY_THRESHOLD)
        
        chunks = []
        sentence_positions = self._map_sentence_positions(sentences, full_text)
        
        for i, cluster_indices in enumerate(clusters):
            cluster_sentences = [sentences[idx] for idx in cluster_indices]
            chunk_text = ' '.join(cluster_sentences).strip()
            
            # 🔥 MIN_CHUNK_SIZE 제약 완화 (20자 이상이면 OK)
            if len(chunk_text) >= MIN_CHUNK_SIZE:
                page_span = self._calculate_page_span_from_sentences(
                    cluster_indices, sentence_positions, page_mapping
                )
                
                chunk = Chunk(
                    id=f"{filename}_semantic_chunk_{i+1}",
                    content=chunk_text,
                    page_number=page_span[0] if page_span else 1,
                    page_span=page_span
                )
                chunks.append(chunk)
        
        return chunks
    
    def _map_sentence_positions(self, sentences: List[str], full_text: str) -> List[dict]:
        """문장들의 전체 텍스트 내 위치 계산"""
        positions = []
        search_start = 0
        
        for sentence in sentences:
            start_pos = full_text.find(sentence, search_start)
            if start_pos != -1:
                end_pos = start_pos + len(sentence)
                positions.append({'start': start_pos, 'end': end_pos})
                search_start = end_pos
            else:
                positions.append({'start': search_start, 'end': search_start})
        
        return positions
    
    def _calculate_page_span(self, chunk_text: str, full_text: str, page_mapping: List[dict]) -> List[int]:
        """청크가 걸쳐있는 페이지들 계산"""
        # 청크의 전체 텍스트 내 위치 찾기
        chunk_start = full_text.find(chunk_text)
        if chunk_start == -1:
            return [1]  # 기본값
        
        chunk_end = chunk_start + len(chunk_text)
        
        # 겹치는 페이지들 찾기
        involved_pages = []
        for page_info in page_mapping:
            page_start = page_info['start']
            page_end = page_info['end']
            
            # 청크와 페이지가 겹치는지 확인
            if not (chunk_end <= page_start or chunk_start >= page_end):
                involved_pages.append(page_info['page_num'])
        
        return sorted(list(set(involved_pages))) if involved_pages else [1]
    
    def _calculate_page_span_from_sentences(self, cluster_indices: List[int], 
                                           sentence_positions: List[dict], 
                                           page_mapping: List[dict]) -> List[int]:
        """문장 클러스터가 걸쳐있는 페이지들 계산"""
        if not cluster_indices:
            return [1]
        
        # 클러스터의 시작과 끝 위치
        cluster_start = sentence_positions[cluster_indices[0]]['start']
        cluster_end = sentence_positions[cluster_indices[-1]]['end']
        
        # 겹치는 페이지들 찾기
        involved_pages = []
        for page_info in page_mapping:
            page_start = page_info['start']
            page_end = page_info['end']
            
            if not (cluster_end <= page_start or cluster_start >= page_end):
                involved_pages.append(page_info['page_num'])
        
        return sorted(list(set(involved_pages))) if involved_pages else [1]
    
    def _analyze_chunks(self, chunks: List[Chunk], method_name: str) -> ChunkDebugInfo:
        """청크 분석"""
        total_chunks = len(chunks)
        print(f"📈 {method_name.upper()} 청킹 결과: {total_chunks}개")
        
        # 페이지별 분포 계산 (시작 페이지만 카운트)
        page_distribution = {}
        for chunk in chunks:
            start_page = chunk.page_number  # 시작 페이지만 카운트
            page_distribution[start_page] = page_distribution.get(start_page, 0) + 1
        
        # 페이지별 분포 출력
        self._print_page_distribution(page_distribution)
        
        # 크기별 분포
        size_ranges = {
            'tiny (< 100자)': 0, 'small (100-300자)': 0, 'medium (300-600자)': 0,
            'large (600-1000자)': 0, 'xlarge (> 1000자)': 0
        }
        
        for chunk in chunks:
            size = len(chunk.content)
            if size < 100: size_ranges['tiny (< 100자)'] += 1
            elif size < 300: size_ranges['small (100-300자)'] += 1
            elif size < 600: size_ranges['medium (300-600자)'] += 1
            elif size < 1000: size_ranges['large (600-1000자)'] += 1
            else: size_ranges['xlarge (> 1000자)'] += 1
        
        # 품질 체크
        empty_chunks = sum(1 for chunk in chunks if not chunk.content.strip())
        content_set = set()
        duplicate_chunks = 0
        for chunk in chunks:
            content_hash = hash(chunk.content.strip())
            if content_hash in content_set:
                duplicate_chunks += 1
            else:
                content_set.add(content_hash)
        
        print(f"📏 크기별 분포:")
        for range_name, count in size_ranges.items():
            percentage = (count / total_chunks) * 100 if total_chunks > 0 else 0
            print(f"   {range_name}: {count}개 ({percentage:.1f}%)")
        
        print(f"🚨 품질 이슈:")
        print(f"   빈 청크: {empty_chunks}개")
        print(f"   중복 청크: {duplicate_chunks}개")
        
        return ChunkDebugInfo(
            total_chunks=total_chunks,
            page_distribution=page_distribution,
            size_distribution=size_ranges,
            empty_chunks=empty_chunks,
            duplicate_chunks=duplicate_chunks,
            similarity_scores=[],
            method_name=method_name
        )
    
    def _print_page_distribution(self, page_distribution: Dict[int, int]):
        """페이지별 분포 출력 (별도 함수로 분리)"""
        print(f"📄 페이지별 청크 분포:")
        for page_num in sorted(page_distribution.keys()):
            count = page_distribution[page_num]
            print(f"   Page {page_num}: {count}개 청크")
    
    def _get_cache_data(self, filename: str) -> dict:
        """캐시에서 데이터 가져오기"""
        from ..file.routers import GLOBAL_PDF_CACHE
        
        if filename not in GLOBAL_PDF_CACHE:
            raise ValueError(f"PDF 캐시를 찾을 수 없습니다: {filename}")
        return GLOBAL_PDF_CACHE[filename]
    
    def _extract_page_content(self, page_text: str) -> Tuple[int, str]:
        """페이지 번호와 내용 추출"""
        match = re.match(r'## 📄 페이지 (\d+)\n\n(.*)', page_text, re.DOTALL)
        if match:
            page_num = int(match.group(1))
            content = match.group(2).strip()
            return page_num, content
        else:
            return 1, page_text.strip()
    
    def _split_sentences(self, text: str) -> List[str]:
        """문장 분할"""
        sentence_endings = r'[.!?。！？]+\s*'
        sentences = re.split(sentence_endings, text)
        
        return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
    
    def _cluster_sentences(self, sentences: List[str], threshold: float) -> List[List[int]]:
        """문장 클러스터링"""
        if len(sentences) <= 1:
            return [[0]] if sentences else []
        
        if self.chunking_method == 'cosine':
            sentence_vectors = self._create_vectors(sentences)
        
        clusters = [[0]]
        
        for i in range(1, len(sentences)):
            if self.chunking_method == 'cosine':
                similarity = self._cosine_similarity(sentence_vectors[i-1], sentence_vectors[i])
            else:  # jaccard
                similarity = self._jaccard_similarity(sentences[i-1], sentences[i])

            if similarity < threshold:
                clusters.append([])
            
            clusters[-1].append(i)
            
            # 최대 크기 제한
            current_text = ' '.join([sentences[idx] for idx in clusters[-1]])
            if len(current_text) > MAX_CHUNK_SIZE and len(clusters[-1]) > 1:
                clusters[-1].pop()
                clusters.append([i])
        
        return clusters
    
    def _create_vectors(self, sentences: List[str]) -> List[np.ndarray]:
        """TF-IDF 벡터 생성"""
        all_words = set()
        sentence_words = []
        
        for sentence in sentences:
            words = self._tokenize(sentence)
            sentence_words.append(words)
            all_words.update(words)
        
        vocab = list(all_words)
        word_to_idx = {word: idx for idx, word in enumerate(vocab)}
        
        doc_freq = Counter()
        for words in sentence_words:
            for word in set(words):
                doc_freq[word] += 1
        
        vectors = []
        for words in sentence_words:
            vector = np.zeros(len(vocab))
            word_count = Counter(words)
            
            for word, count in word_count.items():
                if word in word_to_idx:
                    idx = word_to_idx[word]
                    tf = count / len(words)
                    idf = math.log(len(sentences) / (doc_freq[word] + 1))
                    vector[idx] = tf * idf
            
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = vector / norm
            
            vectors.append(vector)
        
        return vectors
    
    def _tokenize(self, text: str) -> List[str]:
        """토큰화"""
        clean_text = re.sub(r'[^\w\s가-힣]', ' ', text)
        words = clean_text.lower().split()
        
        stopwords = {
            '이', '그', '저', '것', '수', '등', '및', '또는', '그리고', '하지만', '그러나',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'
        }
        
        return [word for word in words if word not in stopwords and len(word) > 1]
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """코사인 유사도"""
        return float(np.dot(vec1, vec2))
    
    def _jaccard_similarity(self, sent1: str, sent2: str) -> float:
        """자카드 유사도"""
        w1 = set(self._tokenize(sent1))
        w2 = set(self._tokenize(sent2))
        if not w1 or not w2:
            return 0.0
        return len(w1.intersection(w2)) / len(w1.union(w2))
    
