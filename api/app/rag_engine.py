# api/app/rag_engine.py
import re
import math
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from collections import Counter
from .doc_chunker import Chunk

@dataclass
class SearchResult:
    chunk: Chunk
    score: float
    citation: str

class SearchIndex:
    """TF-IDF 기반 검색 인덱스"""
    
    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks
        self.doc_freq = Counter()  # 단어별 문서 빈도
        self.chunk_words = []      # 청크별 단어 리스트
        self.vocab = set()         # 전체 어휘
        
        self._build_index()
    
    def _build_index(self):
        """검색 인덱스 구축"""
        print(f"🔍 검색 인덱스 구축 시작: {len(self.chunks)}개 청크")
        
        # 1. 각 청크의 단어들 추출
        for chunk in self.chunks:
            words = self._tokenize(chunk.content)
            self.chunk_words.append(words)
            self.vocab.update(words)
            
            # 문서 빈도 계산 (청크별로 단어가 나타나는지만 체크)
            unique_words = set(words)
            for word in unique_words:
                self.doc_freq[word] += 1
        
        print(f"✅ 인덱스 완료: 어휘 {len(self.vocab)}개, 평균 {sum(len(w) for w in self.chunk_words)/len(self.chunk_words):.1f}단어/청크")
    
    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Top-k 검색 수행"""
        query_words = self._tokenize(query)
        if not query_words:
            return []
        
        scores = []
        
        # 각 청크에 대해 TF-IDF 점수 계산
        for i, chunk in enumerate(self.chunks):
            score = self._calculate_tfidf_score(query_words, self.chunk_words[i])
            if score > 0:  # 관련성이 있는 청크만
                scores.append((score, i))
        
        # 점수 순으로 정렬하고 상위 k개 선택
        scores.sort(reverse=True)
        top_results = scores[:top_k]
        
        # SearchResult 객체로 변환
        results = []
        for rank, (score, chunk_idx) in enumerate(top_results, 1):
            chunk = self.chunks[chunk_idx]
            citation = f"[{rank}] (Page {chunk.page_number})"
            
            result = SearchResult(
                chunk=chunk,
                score=score,
                citation=citation
            )
            results.append(result)
        
        print(f"🔍 검색 완료: '{query}' → {len(results)}개 결과")
        return results
    
    def _calculate_tfidf_score(self, query_words: List[str], doc_words: List[str]) -> float:
        """TF-IDF 점수 계산"""
        if not doc_words:
            return 0.0
        
        doc_word_count = Counter(doc_words)
        doc_length = len(doc_words)
        total_docs = len(self.chunks)
        
        score = 0.0
        
        for query_word in query_words:
            if query_word not in doc_word_count:
                continue
            
            # TF 계산 (정규화된 빈도)
            tf = doc_word_count[query_word] / doc_length
            
            # IDF 계산
            doc_freq = self.doc_freq.get(query_word, 0)
            if doc_freq > 0:
                idf = math.log(total_docs / doc_freq)
            else:
                idf = 0
            
            # TF-IDF 점수
            score += tf * idf
        
        return score
    
    def _tokenize(self, text: str) -> List[str]:
        """한글/영문 토큰화"""
        # 특수문자 제거하고 소문자 변환
        clean_text = re.sub(r'[^\w\s가-힣]', ' ', text)
        words = clean_text.lower().split()
        
        # 불용어 제거
        stopwords = {
            '이', '그', '저', '것', '수', '등', '및', '또는', '그리고', '하지만', '그러나',
            '있다', '없다', '이다', '아니다', '한다', '된다', '같다', '다른', '많다', '적다',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did'
        }
        
        # 2글자 이상이고 불용어가 아닌 단어만 유지
        return [word for word in words if len(word) > 1 and word not in stopwords]


class CitationFormatter:
    """인용 형식 처리"""
    
    @staticmethod
    def format_chunks_with_citations(results: List[SearchResult]) -> str:
        """검색 결과를 인용 형식으로 포맷팅"""
        if not results:
            return "관련 정보를 찾을 수 없습니다."
        
        formatted_chunks = []
        for result in results:
            citation = result.citation
            content = result.chunk.content[:500] + "..." if len(result.chunk.content) > 500 else result.chunk.content
            formatted_chunks.append(f"{citation}: {content}")
        
        return "\n\n".join(formatted_chunks)
    
    @staticmethod
    def create_system_prompt(chunks_text: str, filename: str, query: str) -> str:
        """인용 지시가 포함된 시스템 프롬프트 생성"""
        return f"""당신은 PDF 문서 분석 전문가입니다.
다음 관련 문서 구간을 바탕으로 질문에 답변하되, 반드시 인용 형식을 사용하세요.

문서명: {filename}
질문: {query}

관련 구간:
{chunks_text}

답변 규칙:
1. 반드시 [번호] (Page X) 형식으로 출처를 명시하세요
2. 구체적인 내용을 인용하여 답변하세요
3. 관련 구간에서 찾을 수 없는 내용은 추측하지 마세요"""
    
    @staticmethod
    def create_fallback_prompt(filename: str, query: str) -> str:
        """검색 결과가 없을 때 전체 문서용 프롬프트"""
        return f"""당신은 PDF 문서 분석 전문가입니다.
문서명: {filename}
질문: {query}

검색된 관련 구간이 없어 전체 문서를 참조합니다.
문서에서 직접 확인할 수 있는 내용을 구체적으로 인용하고, 페이지 번호를 참조해주세요."""



def search_and_format(search_index: SearchIndex, query: str, filename: str, top_k: int = 5) -> Tuple[str, List[SearchResult]]:
    """검색 수행 후 인용 형식으로 포맷팅"""
    results = search_index.search(query, top_k)
    
    if results:
        formatted_text = CitationFormatter.format_chunks_with_citations(results)
        system_prompt = CitationFormatter.create_system_prompt(formatted_text, filename, query)
    else:
        # 검색 결과 없을 때 전체 텍스트용 처리
        system_prompt = CitationFormatter.create_fallback_prompt(filename, query)
    
    return system_prompt, results