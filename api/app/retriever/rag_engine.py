# api/app/rag_engine.py
import re
import math
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from collections import Counter
from .doc_chunker import Chunk
from ..config import PROMPT_BANK
prompts = PROMPT_BANK.get("rag_basic", {})

from .faiss_index import create_faiss_index_from_cache, SearchResult
from ..utils import detect_summary_request
from ..file.cache_manager import pdf_cache_manager, build_page_content_map, get_combined_text_from_cache
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

def extract_specific_pages_content(filename: str, page_numbers: list[int]) -> str:
    """
    캐시에서 특정 페이지들 내용 추출 (복수 페이지 지원)
    
    Args:
        filename: PDF 파일명
        page_numbers: 요청 페이지 번호 리스트
        
    Returns:
        str: 해당 페이지들의 텍스트 내용
    """
    if not page_numbers:
        return "요청된 페이지가 없습니다."
    page_content_map = build_page_content_map(filename)
    
    if not page_content_map:
        raise KeyError("페이지 정보를 찾을 수 없습니다.")
    
    found_pages = []
    missing_pages = []
    
    for page_num in page_numbers:
        if page_num in page_content_map:
            content = page_content_map[page_num]
            found_pages.append(f"=== 페이지 {page_num} ===\n{content}")
        else:
            missing_pages.append(page_num)
    
    result_parts = []
    
    if found_pages:
        result_parts.extend(found_pages)
    
    if missing_pages:
        available_pages = sorted(page_content_map.keys())
        result_parts.append(f"\n⚠️ 찾을 수 없는 페이지: {missing_pages}")
        result_parts.append(f"사용 가능한 페이지: {available_pages}")
    
    return "\n\n".join(result_parts)

def search_with_faiss_engine(filename: str, query: str, top_k: int = 5) -> Tuple[str, List]:
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
        # 1. 쿼리 의도 분석
        is_detected_full_document, page_list = detect_summary_request(query)
        print(f"🎯 전체 문서 활용여부 감지 결과: {is_detected_full_document}")
        
        # 2. 전체 문서 모드
        if is_detected_full_document:
            print(f"📄 전체 문서 모드: {query[:50]}...")
            full_text = get_combined_text_from_cache(filename)
            
            template = prompts.get("full_document_summary", 
                "당신은 PDF 문서 분석 전문가입니다.\n📄 전체 문서 내용:\n{full_text}")
            system_message = template.format(filename=filename, full_text=full_text)
            
            return system_message, []
        # 3. 페이지 특정 모드
        elif page_list:  # 특정 페이지들이 지정된 경우
            print(f"📄 페이지 특정 모드: {page_list} 페이지")
            pages_content = extract_specific_pages_content(filename, page_list)
            
            if len(page_list) == 1:
                page_desc = f"페이지 {page_list[0]}"
            else:
                page_desc = f"{len(page_list)}개 페이지 ({', '.join(map(str, page_list))})"
            
            system_message = f"""당신은 PDF 문서 분석 전문가입니다.
사용자가 요청한 {page_desc}의 내용입니다:

문서명: {filename}
질문: {query}

{pages_content}

위 페이지들의 내용을 바탕으로 사용자의 질문에 정확하고 자세하게 답변해주세요.
페이지 번호를 명시하면서 답변하세요."""
            
            return system_message, []
        
        # 3. FAISS 검색 모드
        print(f"🔍 FAISS 검색 모드: {query[:50]}...")
        faiss_index = create_faiss_index_from_cache(filename)
        
        if not faiss_index:
            print("❌ FAISS 인덱스 생성 실패, 전체 문서 모드로 폴백")
            full_text = get_combined_text_from_cache(filename)
            
            template = prompts.get("no_search_results",
                "검색 결과가 없어 전체 문서를 참조합니다.\n전체 문서 내용:\n{full_text}")
            system_message = template.format(filename=filename, query=query, full_text=full_text)
            
            return system_message, []
        
        # 4. 검색 실행
        search_results = faiss_index.search(query, top_k)
        
        if not search_results:
            print("⚠️ 검색 결과 없음, 전체 문서 모드로 폴백")
            full_text = get_combined_text_from_cache(filename)
            
            template = prompts.get("no_search_results",
                "검색 결과가 없어 전체 문서를 참조합니다.\n전체 문서 내용:\n{full_text}")
            system_message = template.format(filename=filename, query=query, full_text=full_text)
            
            return system_message, []
        
        # 5. 검색 결과 기반 프롬프트
        formatted_results = []
        for result in search_results:
            content_preview = result.chunk.content[:300] + "..." if len(result.chunk.content) > 300 else result.chunk.content
            formatted_results.append(f"{result.citation}: {content_preview} (유사도: {result.score:.3f})")
        
        results_text = "\n\n".join(formatted_results)
        
        template = prompts.get("faiss_search_results",
            "FAISS 검색 결과:\n{results_text}")
        system_message = template.format(filename=filename, query=query, results_text=results_text)
        
        print(f"✅ FAISS 검색 완료: {len(search_results)}개 결과")
        return system_message, search_results
        
    except Exception as e:
        print(f"❌ FAISS 검색 오류: {e}")
        import traceback
        traceback.print_exc()
        
        # 폴백: 전체 문서 모드
        full_text = get_combined_text_from_cache(filename)
        
        template = prompts.get("search_fallback",
            "검색 중 오류 발생하여 전체 문서를 참조합니다.\n오류: {error}\n전체 문서 내용:\n{full_text}")
        system_message = template.format(filename=filename, query=query, error=str(e), full_text=full_text)
        
        return system_message, []


def _ensemble_faiss_tfidf(faiss_results: List, tfidf_results: List, tfidf_weight: float, top_k: int) -> List:
    """
    FAISS와 TF-IDF 결과를 앙상블
    
    Args:
        faiss_results: FAISS 검색 결과
        tfidf_results: TF-IDF 검색 결과
        tfidf_weight: TF-IDF 가중치 (FAISS 가중치는 1 - tfidf_weight)
        top_k: 최종 반환할 결과 수
        
    Returns:
        List: 앙상블된 최종 검색 결과
    """
    faiss_weight = 1.0 - tfidf_weight
    
    # 점수 맵 생성
    chunk_scores = {}  # chunk_id -> 최종 점수
    chunk_objects = {}  # chunk_id -> SearchResult 객체
    
    # FAISS 결과 처리 (점수 그대로 사용)
    for result in faiss_results:
        chunk_id = result.chunk.id
        chunk_scores[chunk_id] = result.score * faiss_weight
        chunk_objects[chunk_id] = result
    
    # TF-IDF 결과 처리 (정규화 필요)
    if tfidf_results:
        # TF-IDF 점수 정규화 (0-1 범위로)
        max_tfidf_score = max(r.score for r in tfidf_results)
        
        for result in tfidf_results:
            chunk_id = result.chunk.id
            normalized_score = result.score / max_tfidf_score if max_tfidf_score > 0 else 0
            
            if chunk_id in chunk_scores:
                # 이미 FAISS에 있으면 TF-IDF 점수 추가
                chunk_scores[chunk_id] += normalized_score * tfidf_weight
            else:
                # TF-IDF만 있으면 TF-IDF 점수만
                chunk_scores[chunk_id] = normalized_score * tfidf_weight
                chunk_objects[chunk_id] = result
    
    # 점수순 정렬
    sorted_chunks = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)
    
    # 최종 결과 생성
    final_results = []
    for i, (chunk_id, final_score) in enumerate(sorted_chunks[:top_k]):
        if chunk_id in chunk_objects:
            original_result = chunk_objects[chunk_id]
            
            # 새로운 SearchResult 생성 (앙상블 점수와 새 citation으로)
            ensemble_result = SearchResult(
                chunk=original_result.chunk,
                score=final_score,
                citation=f"[{i+1}] (Page {original_result.chunk.page_number})"
            )
            final_results.append(ensemble_result)
    
    return final_results
