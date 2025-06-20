# api/app/rag_monitor.py
"""
Phoenix 기반 RAG 성능 자동 모니터링 - Flat Structure
각 chunk를 독립 row로 표시 + AI 결과 추가 + 누적 저장
"""

import os
import time
from pathlib import Path
from typing import List
import hashlib
from datetime import datetime

import phoenix as px
from phoenix import Client

from .rag_engine import SearchResult

class SeamlessRAGMonitor:
    """chat-with-pdf와 완전 통합된 RAG 모니터링 (Flat Structure)"""

    def __init__(self):
        self.phoenix_started = False
        self.project_name = "chatx-seamless-monitoring"
        self.client: Client = None
        self.session_cache = {}  # filename별 세션 관리
        self._start_phoenix_safe()
        self._setup_tracer()

    def _start_phoenix_safe(self):
        """윈도우 권한 이슈 해결 & Phoenix 앱 구동 + Client 초기화"""
        db_path = Path.home() / ".phoenix" / "phoenix.db"
        db_path.parent.mkdir(exist_ok=True)

        # 호스트/포트/DB URL 환경변수 설정
        os.environ["PHOENIX_HOST"]             = "0.0.0.0"
        os.environ["PHOENIX_PORT"]             = "6006"
        os.environ["PHOENIX_SQL_DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["PHOENIX_PROJECT_NAME"]     = self.project_name

        try:
            px.launch_app()
            self.client = px.Client()
            self.phoenix_started = True
            print(f"🎯 Phoenix 대시보드: http://{os.environ['PHOENIX_HOST']}:{os.environ['PHOENIX_PORT']}")
            print(f"📁 DB 경로: {db_path}")
        except Exception as e:
            print(f"⚠️ Phoenix 시작 실패: {e}")

    def _setup_tracer(self):
        """OpenTelemetry 트레이서를 Phoenix endpoint로 설정"""
        if not self.phoenix_started:
            return
            
        try:
            from phoenix.otel import register
            
            tracer_provider = register(
                project_name=self.project_name,
                endpoint="http://localhost:6006/v1/traces"
            )
            
            print(f"🔍 Phoenix Tracer 설정완료: {self.project_name}")
            
        except Exception as e:
            print(f"⚠️ Tracer 설정 실패: {e}")

    def _get_session_id(self, filename: str) -> str:
        """filename 기반 세션 ID 생성"""
        if filename not in self.session_cache:
            # filename 해시로 고유 세션 생성
            hash_obj = hashlib.md5(filename.encode())
            session_id = hash_obj.hexdigest()[:8]
            self.session_cache[filename] = {
                'session_id': session_id,
                'query_count': 0,
                'start_time': datetime.now()
            }
        
        return self.session_cache[filename]['session_id']

    def auto_monitor_with_results(
        self,
        query: str,
        filename: str,
        search_results: List[SearchResult],
        search_time_ms: float = 0
    ) -> None:
        """
        🔥 이전 좋았던 구조 복원 + span kind만 추가
        """
        if not (self.phoenix_started and self.client and search_results):
            return

        try:
            from opentelemetry import trace
            from phoenix.trace import using_project
            
            # 세션 정보
            session_id = self._get_session_id(filename)
            self.session_cache[filename]['query_count'] += 1
            query_num = self.session_cache[filename]['query_count']
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            with using_project(self.project_name):
                tracer = trace.get_tracer(__name__)
                
                # 1. 각 chunk를 독립 row로 생성 (이전 구조 복원)
                for i, result in enumerate(search_results):
                    chunk_name = f"chunk_{i+1}"
                    
                    with tracer.start_as_current_span(chunk_name) as chunk_span:
                        # Span Kind 설정 (이슈2 해결)
                        chunk_span.set_attribute("openinference.span.kind", "RETRIEVER")
                        
                        # 이전처럼 input/output 모두 제대로 설정
                        input_text = f"Q{query_num}: {query} | Rank #{i+1}"
                        output_text = result.chunk.content  # 전체 내용
                        
                        chunk_span.set_attribute("input.value", input_text)
                        chunk_span.set_attribute("output.value", output_text)
                        
                        # 세션 정보 (이슈1 해결 - 모든 span에 추가)
                        chunk_span.set_attribute("session_id", session_id)
                        chunk_span.set_attribute("filename", filename)
                        chunk_span.set_attribute("query_number", query_num)
                        chunk_span.set_attribute("chunk_rank", i + 1)
                        chunk_span.set_attribute("similarity_score", float(result.score))
                        chunk_span.set_attribute("chunk_id", result.chunk.id)
                        chunk_span.set_attribute("content_length", len(result.chunk.content))
                        chunk_span.set_attribute("search_time_ms", search_time_ms)
                        chunk_span.set_attribute("timestamp", timestamp)
                        
                        if hasattr(result.chunk, 'page_number'):
                            chunk_span.set_attribute("page_number", result.chunk.page_number)
                
                # 2. AI 결과 row 생성
                with tracer.start_as_current_span("ai_response") as ai_span:
                    # Span Kind 설정 (이슈2 해결)
                    ai_span.set_attribute("openinference.span.kind", "LLM")
                    
                    # 컨텍스트 생성 (Top 3 chunks)
                    context_chunks = []
                    for i, result in enumerate(search_results[:3]):
                        context_chunks.append(f"[{i+1}] Score: {result.score:.3f}\n{result.chunk.content[:200]}...")
                    
                    full_context = "\n\n".join(context_chunks)
                    
                    # Input/Output 제대로 설정
                    ai_input = f"Q{query_num}: {query}\n\nTop-{len(search_results)} Context:\n{full_context[:300]}..."
                    ai_output = f"[AI 응답 대기중...] Based on {len(search_results)} retrieved chunks\n\n상세 컨텍스트:\n{full_context}"
                    
                    ai_span.set_attribute("input.value", ai_input)
                    ai_span.set_attribute("output.value", ai_output)
                    
                    # 세션 정보 추가
                    ai_span.set_attribute("session_id", session_id)
                    ai_span.set_attribute("filename", filename)
                    ai_span.set_attribute("query_number", query_num)
                    ai_span.set_attribute("model_name", "gpt-4o")
                    ai_span.set_attribute("retrieved_chunks_count", len(search_results))
                    ai_span.set_attribute("search_time_ms", search_time_ms)
                    ai_span.set_attribute("timestamp", timestamp)
                    
                    # 통계 정보
                    avg_score = sum(float(r.score) for r in search_results) / len(search_results)
                    top_score = max(float(r.score) for r in search_results)
                    ai_span.set_attribute("avg_similarity", f"{avg_score:.3f}")
                    ai_span.set_attribute("top_similarity", f"{top_score:.3f}")
                
                print(f"📊 Phoenix 모니터링: Q{query_num} '{query[:20]}...' → {len(search_results)+1}개 row 누적")
                
        except Exception as e:
            print(f"⚠️ Phoenix 모니터링 조용히 스킵: {e}")

    def update_ai_response(self, query: str, filename: str, ai_response: str, token_usage: dict = None):
        """
        🔄 AI 응답 완료 후 해당 row 업데이트 (향후 사용)
        """
        # 나중에 실제 AI 응답으로 업데이트하는 함수
        pass

    def _detect_metadata_bias(self, results: List[SearchResult]) -> bool:
        """메타데이터 편향 감지"""
        if not results:
            return False
        text = results[0].chunk.content.lower()
        indicators = ["page","copyright","footer","header","목차","페이지","©","저작권","부록","참고문헌"]
        return sum(1 for kw in indicators if kw in text) >= 2

# 싱글톤 인스턴스
_monitor_instance: SeamlessRAGMonitor = None

def get_monitor() -> SeamlessRAGMonitor:
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = SeamlessRAGMonitor()
    return _monitor_instance

def auto_monitor_chat(
    query: str,
    filename: str,
    search_results: List[SearchResult],
    search_time_ms: float = 0
):
    """chat-with-pdf 자동 호출 헬퍼"""
    get_monitor().auto_monitor_with_results(query, filename, search_results, search_time_ms)

if __name__ == "__main__":
    mon = SeamlessRAGMonitor()
    print("✅ Phoenix Flat Structure 모니터링 시스템 준비완료!")
    print("📋 구조: 각 chunk + AI 결과가 메인뷰에서 독립 row로 표시")
    print("🔄 누적: 동일 세션 내 질문별로 계속 쌓임")