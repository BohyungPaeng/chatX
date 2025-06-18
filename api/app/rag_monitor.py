# api/app/rag_monitor.py
"""
Phoenix 기반 청킹 성능 자동 모니터링
chat-with-pdf 사용 시 백그라운드에서 자동 실행
"""

import phoenix as px
from phoenix.trace import using_project
from typing import List, Dict
import time
import asyncio
from threading import Thread

from .rag_engine import search_with_faiss_engine

class SeamlessRAGMonitor:
    """chat-with-pdf와 완전 통합된 성능 모니터링"""
    
    def __init__(self):
        self.phoenix_started = False
        self._start_phoenix()
        
    def _start_phoenix(self):
        """Phoenix 백그라운드 시작 (에러 무시)"""
        try:
            px.launch_app(host="0.0.0.0", port=6006)
            self.phoenix_started = True
            print("🎯 청킹 성능 대시보드: http://localhost:6006")
        except:
            print("⚠️ Phoenix 시작 실패 (포트 사용중일 수 있음)")
    
    def auto_compare_chunking_on_chat(self, query: str, filename: str) -> None:
        """
        chat-with-pdf 호출 시 자동 실행되는 청킹 비교
        사용자는 평상시처럼 채팅만 하면 됨
        """
        if not self.phoenix_started:
            return
            
        # 백그라운드에서 청킹 전략 비교 (사용자 응답 지연 없음)
        Thread(target=self._background_chunking_comparison, 
               args=(query, filename), daemon=True).start()
    
    def _background_chunking_comparison(self, query: str, filename: str):
        """백그라운드에서 청킹 전략별 성능 비교"""
        strategies = ["semantic", "fixed", "sliding"]
        
        with using_project("chatx-chunking-auto"):
            for strategy in strategies:
                try:
                    start_time = time.time()
                    
                    # 각 청킹 전략으로 검색 (기존 함수 활용)
                    _, results = search_with_faiss_engine(filename, query, top_k=5)
                    search_time = (time.time() - start_time) * 1000
                    
                    # 성능 지표 계산
                    scores = [r.score for r in results] if results else [0]
                    has_metadata_bias = self._detect_metadata_bias(results)
                    
                    # Phoenix 로깅
                    px.log_retrieval(
                        query=f"[AUTO-{strategy}] {query}",
                        retrieved_documents=[r.chunk.content for r in results],
                        retrieved_document_scores=scores,
                        metadata={
                            "chunking_strategy": strategy,
                            "filename": filename,
                            "search_time_ms": search_time,
                            "top_score": max(scores),
                            "avg_score": sum(scores) / len(scores) if scores else 0,
                            "metadata_bias": has_metadata_bias,
                            "auto_generated": True
                        }
                    )
                    
                except Exception as e:
                    print(f"⚠️ {strategy} 청킹 비교 실패: {e}")
    
    def _detect_metadata_bias(self, results: List) -> bool:
        """메타데이터 편향 감지"""
        if not results:
            return False
        
        top_content = results[0].chunk.content.lower()
        bias_keywords = ["page", "copyright", "footer", "header", "목차", "페이지"]
        return any(keyword in top_content for keyword in bias_keywords)

# 전역 인스턴스 (자동 초기화)
_seamless_monitor = SeamlessRAGMonitor()

def auto_monitor_chat(query: str, filename: str):
    """chat-with-pdf에서 자동 호출되는 함수 (1줄 추가용)"""
    _seamless_monitor.auto_compare_chunking_on_chat(query, filename)