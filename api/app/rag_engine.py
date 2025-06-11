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

@dataclass 
class ContextInfo:
    """컨텍스트 정보"""
    top1_full_pages: str  # Top-1 결과의 전체 페이지들
    other_chunks: str     # 나머지 청크들
    total_pages_used: int # 사용된 총 페이지 수
    strategy: str         # 사용된 전략

class SearchIndex:
    """TF-IDF 기반 검색 인덱스 - 페이지 컨텍스트 확장 지원"""
    
    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks
        self.doc_freq = Counter()
        self.chunk_words = []
        self.vocab = set()
        self.page_content_map = {}  # 페이지별 전체 내용 매핑
        
        self._build_index()
        self._build_page_map()
    
    def _build_index(self):
        """검색 인덱스 구축"""
        print(f"🔍 검색 인덱스 구축 시작: {len(self.chunks)}개 청크")
        
        for chunk in self.chunks:
            words = self._tokenize(chunk.content)
            self.chunk_words.append(words)
            self.vocab.update(words)
            
            unique_words = set(words)
            for word in unique_words:
                self.doc_freq[word] += 1
        
        print(f"✅ 인덱스 완료: 어휘 {len(self.vocab)}개")
    
    def _build_page_map(self):
        """페이지별 전체 내용 매핑 구축"""
        from .cache_manager import pdf_cache_manager
        
        if self.chunks:
            # 청크 ID에서 파일명 올바르게 추출
            chunk_id = self.chunks[0].id
            # semantic_chunk_ 또는 cosine_chunk_ 등을 제거하여 원본 파일명 추출
            if '_semantic_chunk_' in chunk_id:
                filename = chunk_id.split('_semantic_chunk_')[0]
            elif '_cosine_chunk_' in chunk_id:
                filename = chunk_id.split('_cosine_chunk_')[0]
            elif '_simple_chunk_' in chunk_id:
                filename = chunk_id.split('_simple_chunk_')[0]
            else:
                # fallback: 마지막 _chunk_ 이전까지
                filename = chunk_id.rsplit('_chunk_', 1)[0]
            
            cache_data = pdf_cache_manager.load(filename)
            
            if cache_data and 'page_texts' in cache_data:
                page_texts = cache_data['page_texts']
                
                for page_text in page_texts:
                    page_num, content = self._extract_page_content(page_text)
                    self.page_content_map[page_num] = content
                
                print(f"📄 페이지 맵 구축 완료: {len(self.page_content_map)}개 페이지")
    
    def search_with_page_context(self, query: str, top_k: int = 5) -> Tuple[List[SearchResult], ContextInfo]:
        """페이지 컨텍스트와 함께 검색"""
        results = self.search(query, top_k)
        
        if not results:
            empty_context = ContextInfo("", "", 0, "no_results")
            return results, empty_context
        
        # Top-1 결과의 전체 페이지 스팬 가져오기
        top1_result = results[0]
        top1_pages = top1_result.chunk.page_span or [top1_result.chunk.page_number]
        
        # Top-1의 전체 페이지 내용 수집
        top1_full_content = []
        for page_num in sorted(top1_pages):
            if page_num in self.page_content_map:
                page_content = self.page_content_map[page_num]
                top1_full_content.append(f"=== 페이지 {page_num} ===\n{page_content}")
        
        top1_full_pages = "\n\n".join(top1_full_content)
        
        # 나머지 청크들 (Top-2부터)
        other_chunks_content = []
        for i, result in enumerate(results[1:], 2):
            chunk_preview = result.chunk.content[:300] + "..." if len(result.chunk.content) > 300 else result.chunk.content
            other_chunks_content.append(f"[{i}] (Page {result.chunk.page_number}): {chunk_preview}")
        
        other_chunks = "\n\n".join(other_chunks_content)
        
        context_info = ContextInfo(
            top1_full_pages=top1_full_pages,
            other_chunks=other_chunks,
            total_pages_used=len(top1_pages),
            strategy="top1_full_pages_plus_chunks"
        )
        
        print(f"🎯 컨텍스트: Top-1의 {len(top1_pages)}개 페이지 + {len(results)-1}개 추가 청크")
        
        return results, context_info
    
    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """기본 Top-k 검색"""
        query_words = self._tokenize(query)
        if not query_words:
            return []
        
        scores = []
        
        for i, chunk in enumerate(self.chunks):
            score = self._calculate_tfidf_score(query_words, self.chunk_words[i])
            if score > 0:
                scores.append((score, i))
        
        scores.sort(reverse=True)
        top_results = scores[:top_k]
        
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
            
            tf = doc_word_count[query_word] / doc_length
            doc_freq = self.doc_freq.get(query_word, 0)
            if doc_freq > 0:
                idf = math.log(total_docs / doc_freq)
            else:
                idf = 0
            
            score += tf * idf
        
        return score
    
    def _tokenize(self, text: str) -> List[str]:
        """한글/영문 토큰화"""
        clean_text = re.sub(r'[^\w\s가-힣]', ' ', text)
        words = clean_text.lower().split()
        
        stopwords = {
            '이', '그', '저', '것', '수', '등', '및', '또는', '그리고', '하지만', '그러나',
            '있다', '없다', '이다', '아니다', '한다', '된다', '같다', '다른', '많다', '적다',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did'
        }
        
        return [word for word in words if len(word) > 1 and word not in stopwords]
    
    def _extract_page_content(self, page_text: str) -> Tuple[int, str]:
        """페이지 번호와 내용 추출"""
        match = re.match(r'## 📄 페이지 (\d+)\n\n(.*)', page_text, re.DOTALL)
        if match:
            page_num = int(match.group(1))
            content = match.group(2).strip()
            return page_num, content
        else:
            return 1, page_text.strip()


class CitationFormatter:
    """인용 형식 처리"""
    
    @staticmethod
    def create_system_prompt_with_full_context(context_info: ContextInfo, filename: str, query: str) -> str:
        """전체 컨텍스트용 시스템 프롬프트"""
        return f"""당신은 PDF 문서 분석 전문가입니다.
다음 문서에서 가장 관련성이 높은 페이지 전체와 추가 참고 정보를 제공합니다.

문서명: {filename}
질문: {query}
참조 페이지 수: {context_info.total_pages_used}개

=== 주요 관련 내용 (전체 페이지) ===
{context_info.top1_full_pages}

=== 추가 참고 정보 ===
{context_info.other_chunks}

답변 규칙:
1. **반드시 [1] (Page X) 형식으로 출처를 명시하세요**
2. **주요 관련 내용에서 핵심 정보를 인용하여 답변하세요**
3. **추가 참고 정보도 필요시 [2], [3] 등으로 인용하세요**
4. **문서에서 찾을 수 없는 내용은 "문서에서 해당 정보를 찾을 수 없습니다"라고 명시하세요**"""
    
    @staticmethod
    def create_fallback_prompt(filename: str, query: str) -> str:
        """검색 결과가 없을 때 전체 문서용 프롬프트"""
        from .routers import get_combined_text_from_cache
        full_text = get_combined_text_from_cache(filename)
        return f"""당신은 PDF 문서 분석 전문가입니다.
문서명: {filename}
질문: {query}

검색된 관련 구간이 없어 전체 문서를 참조합니다.

전체 문서 내용:
{full_text}
문서에서 직접 확인할 수 있는 내용을 구체적으로 인용하고, 페이지 번호를 참조해주세요."""
    
    @staticmethod
    def format_chunks_with_citations(results: List[SearchResult]) -> str:
        """기존 포맷터 (호환성 유지)"""
        if not results:
            return "관련 정보를 찾을 수 없습니다."
        
        formatted_chunks = []
        for result in results:
            citation = result.citation
            content = result.chunk.content[:500] + "..." if len(result.chunk.content) > 500 else result.chunk.content
            formatted_chunks.append(f"{citation}: {content}")
        
        return "\n\n".join(formatted_chunks)


# 🎯 Router에서 사용할 통합 함수들
def search_and_generate_system_message(search_index: SearchIndex, query: str, filename: str, 
                                      use_page_context: bool = True, top_k: int = 5) -> Tuple[str, List[SearchResult]]:
    """Router에서 호출할 통합 검색 및 시스템 메시지 생성 함수"""
    
    if use_page_context and search_index.chunks:
        results, context_info = search_index.search_with_page_context(query, top_k)
        
        print(f"🔍 컨텍스트 체크: top1_pages길이={len(context_info.top1_full_pages)}, results={len(results)}")  # 🔧 디버깅
        
        if results and len(context_info.top1_full_pages.strip()) > 0:  # 🔧 조건 수정
            system_message = CitationFormatter.create_system_prompt_with_full_context(context_info, filename, query)
            print(f"🎯 페이지 컨텍스트 모드: {context_info.total_pages_used}개 페이지, {len(results)}개 검색 결과")
        else:
            system_message = CitationFormatter.create_fallback_prompt(filename, query)
            print("⚠️ 페이지 컨텍스트 생성 실패, 전체 문서 모드")
    else:
        # 기존 청크 모드
        results = search_index.search(query, top_k)
        
        if results:
            formatted_text = CitationFormatter.format_chunks_with_citations(results)
            system_message = f"""당신은 PDF 문서 분석 전문가입니다.
다음 PDF 문서({filename})의 관련 구간을 바탕으로 질문에 답변하되, 반드시 인용 형식을 사용하세요.

관련 구간:
{formatted_text}

답변 시 반드시 [번호] (Page X) 형식으로 출처를 명시하세요."""
        else:
            system_message = CitationFormatter.create_fallback_prompt(filename, query)
        
        print(f"🔍 청크 모드: {len(results)}개 검색 결과")
    
    return system_message, results


# 🔄 기존 함수는 호환성을 위해 유지
def search_and_format(search_index: SearchIndex, query: str, filename: str, top_k: int = 5) -> Tuple[str, List[SearchResult]]:
    """기존 함수 (호환성 유지)"""
    return search_and_generate_system_message(search_index, query, filename, use_page_context=False, top_k=top_k)

# api/app/rag_engine.py에 추가할 함수들

# 기존 imports에 추가
from .faiss_index import FaissIndex, create_faiss_index_from_cache, SearchResult as FaissSearchResult

# 요약 키워드 감지
SUMMARY_KEYWORDS = [
    '요약', '전체', '개요', '주요 내용', '핵심', '전반적', '종합',
    'summary', 'summarize', 'overview', 'main points', 'key points', 'overall'
]

def detect_summary_request(query: str) -> bool:
    """요약 요청 감지"""
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in SUMMARY_KEYWORDS)

def get_combined_text_from_cache_safe(filename: str) -> str:
    """안전한 전체 문서 텍스트 가져오기"""
    try:
        from .routers import get_combined_text_from_cache
        return get_combined_text_from_cache(filename)
    except Exception as e:
        print(f"Error getting combined text: {e}")
        return ""

def search_with_faiss_engine(filename: str, query: str, top_k: int = 5) -> Tuple[str, List[FaissSearchResult]]:
    """
    FAISS 기반 검색 및 시스템 메시지 생성
    
    Args:
        filename: PDF 파일명
        query: 사용자 쿼리
        top_k: 반환할 검색 결과 수
        
    Returns:
        Tuple[str, List[FaissSearchResult]]: (시스템 메시지, 검색 결과)
    """
    try:
        # 1. 요약 요청 감지 → 전체 문서 모드
        if detect_summary_request(query):
            print(f"🎯 Summary request detected: {query[:50]}...")
            full_text = get_combined_text_from_cache_safe(filename)
            
            system_message = f"""당신은 PDF 문서 분석 전문가입니다.
다음 PDF 문서({filename})의 전체 내용을 바탕으로 사용자의 요청에 정확하고 자세하게 답변해주세요.

📄 전체 문서 내용:
{full_text}

답변 시 문서에서 직접 확인할 수 있는 내용을 구체적으로 인용하고, 페이지 번호를 참조해주세요.
메타데이터나 바닥글이 아닌 실제 문서의 핵심 내용을 중심으로 답변해주세요."""

            return system_message, []
        
        # 2. FAISS 검색 실행
        print(f"🔍 FAISS search for: {query[:50]}...")
        faiss_index = create_faiss_index_from_cache(filename)
        
        if not faiss_index:
            print("❌ FAISS index creation failed, falling back to full document")
            full_text = get_combined_text_from_cache_safe(filename)
            
            system_message = f"""당신은 PDF 문서 분석 전문가입니다.
FAISS 검색을 사용할 수 없어 전체 문서를 참조합니다.

문서명: {filename}
질문: {query}

전체 문서 내용:
{full_text}

답변 시 문서에서 직접 확인할 수 있는 내용을 구체적으로 인용하고, 페이지 번호를 참조해주세요."""
            
            return system_message, []
        
        # 3. 검색 결과 처리
        search_results = faiss_index.search(query, top_k)
        
        if not search_results:
            print("⚠️ No search results found, using full document")
            full_text = get_combined_text_from_cache_safe(filename)
            
            system_message = f"""당신은 PDF 문서 분석 전문가입니다.
검색 결과가 없어 전체 문서를 참조합니다.

문서명: {filename}
질문: {query}

전체 문서 내용:
{full_text}

답변 시 문서에서 직접 확인할 수 있는 내용을 구체적으로 인용하고, 페이지 번호를 참조해주세요."""
            
            return system_message, []
        
        # 4. 검색 결과 기반 시스템 메시지 생성
        formatted_results = []
        for result in search_results:
            content_preview = result.chunk.content[:300] + "..." if len(result.chunk.content) > 300 else result.chunk.content
            formatted_results.append(f"{result.citation}: {content_preview} (유사도: {result.score:.3f})")
        
        results_text = "\n\n".join(formatted_results)
        
        system_message = f"""당신은 PDF 문서 분석 전문가입니다.
다음 PDF 문서({filename})에서 관련성이 높은 구간을 FAISS 임베딩 검색으로 찾았습니다.

질문: {query}

🎯 관련 구간 (유사도 기반 정렬):
{results_text}

답변 규칙:
1. **반드시 [1] (Page X) 형식으로 출처를 명시하세요**
2. **관련 구간에서 핵심 정보를 인용하여 답변하세요**  
3. **유사도 점수가 높은 순서대로 우선 참조하세요**
4. **문서에서 찾을 수 없는 내용은 "문서에서 해당 정보를 찾을 수 없습니다"라고 명시하세요**"""

        print(f"✅ FAISS search completed: {len(search_results)} results")
        return system_message, search_results
        
    except Exception as e:
        print(f"❌ Error in FAISS search: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback to full document
        full_text = get_combined_text_from_cache_safe(filename)
        system_message = f"""당신은 PDF 문서 분석 전문가입니다.
검색 중 오류가 발생하여 전체 문서를 참조합니다.

문서명: {filename}
질문: {query}
오류: {str(e)}

전체 문서 내용:
{full_text}

답변 시 문서에서 직접 확인할 수 있는 내용을 구체적으로 인용하고, 페이지 번호를 참조해주세요."""
        
        return system_message, []

def search_with_hybrid_engine(filename: str, query: str, top_k: int = 5, 
                             use_faiss: bool = True, use_tfidf: bool = False) -> Tuple[str, List]:
    """
    하이브리드 검색 엔진 (FAISS + TF-IDF 선택 가능)
    
    Args:
        filename: PDF 파일명
        query: 사용자 쿼리 
        top_k: 반환할 검색 결과 수
        use_faiss: FAISS 검색 사용 여부
        use_tfidf: TF-IDF 검색 사용 여부 (기존 방식)
        
    Returns:
        Tuple[str, List]: (시스템 메시지, 검색 결과)
    """
    if use_faiss:
        return search_with_faiss_engine(filename, query, top_k)
    elif use_tfidf:
        # 기존 TF-IDF 방식 사용
        from .doc_chunker import DocumentChunker
        chunks = DocumentChunker('cosine').chunk_document(filename)
        search_index = SearchIndex(chunks)
        return search_and_generate_system_message(search_index, query, filename, use_page_context=True, top_k=top_k)
    else:
        # 전체 문서 모드
        full_text = get_combined_text_from_cache_safe(filename)
        system_message = f"""당신은 PDF 문서 분석 전문가입니다.
검색 없이 전체 문서를 참조합니다.

문서명: {filename}
질문: {query}

전체 문서 내용:
{full_text}

답변 시 문서에서 직접 확인할 수 있는 내용을 구체적으로 인용하고, 페이지 번호를 참조해주세요."""
        
        return system_message, []