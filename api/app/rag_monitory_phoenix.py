# api/app/rag_monitor_phoenix_enhanced.py
"""
Phoenix 기반 RAG 성능 자동 모니터링 - OpenInference 표준 완전 준수
🎯 목표: 두 번째 스크린샷 수준의 풍부한 대시보드 구현
"""
import os
import time
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import asdict

import phoenix as px
from phoenix import Client
from .rag_engine import SearchResult


class PhoenixRAGMonitor:
    """Phoenix 기반 고도화된 RAG 모니터링 - 실제 작동 보장"""
    
    def __init__(self):
        self.phoenix_started = False
        self.project_name = "chatx-seamless-monitoring"
        self.client: Client = None
        self.session_cache = {}
        self.ai_response_cache = {}  # AI 응답 임시 저장용
        self._start_phoenix_safe()
        self._setup_tracer()
    
    def _start_phoenix_safe(self):
        """Phoenix 앱 구동 + Client 초기화 - 에러 방지"""
        db_path = Path.home() / ".phoenix" / "phoenix.db"
        db_path.parent.mkdir(exist_ok=True)
        
        os.environ.update({
            "PHOENIX_HOST": "0.0.0.0",
            "PHOENIX_PORT": "6006", 
            "PHOENIX_SQL_DATABASE_URL": f"sqlite:///{db_path}",
            "PHOENIX_PROJECT_NAME": self.project_name
        })
        
        try:
            px.launch_app()
            self.client = px.Client()
            self.phoenix_started = True
            print(f"🎯 Phoenix 대시보드: http://localhost:6006")
            print(f"📁 DB 경로: {db_path}")
        except Exception as e:
            print(f"⚠️ Phoenix 시작 실패: {e}")
    
    def _setup_tracer(self):
        """OpenTelemetry 트레이서 설정"""
        if not self.phoenix_started:
            return
            
        try:
            from phoenix.otel import register
            register(
                project_name=self.project_name,
                endpoint="http://localhost:6006/v1/traces"
            )
            print(f"🔍 Phoenix Tracer 설정 완료")
        except Exception as e:
            print(f"⚠️ Tracer 설정 실패: {e}")
    
    def _get_session_id(self, filename: str) -> str:
        """파일명 기반 세션 ID 생성"""
        if filename not in self.session_cache:
            session_id = hashlib.md5(filename.encode()).hexdigest()[:8]
            self.session_cache[filename] = {
                'session_id': session_id,
                'query_count': 0,
                'start_time': datetime.now()
            }
        return self.session_cache[filename]['session_id']
    def _evaluate_with_llm_classify(self, query: str, search_results: List[SearchResult], ai_response: str) -> Dict[str, Any]:
        """🔥 phoenix.evals.llm_classify 사용"""
        import pandas as pd
        from phoenix.evals import llm_classify
        
        evaluations = {}
        
        try:
            # 검색 컨텍스트 구성
            search_content = "\n".join([r.chunk.content[:200] for r in search_results[:3]])
            
            # DataFrame 구성 (llm_classify 요구사항)
            eval_df = pd.DataFrame([{
                'input': query,
                'output': ai_response,
                'retrieved_context': search_content
            }])
            
            # 1. Hallucination 평가
            try:
                # OpenAIModel 대신 기본 모델 사용 또는 Azure 모델
                hallucination_eval = llm_classify(
                    dataframe=eval_df,
                    # model=OpenAIModel("gpt-4"),  # 사용 안함
                    template="""
Question: {input}
Reference Context: {retrieved_context}
AI Response: {output}

Does the AI response contain information not supported by the reference context?
Answer: Yes (hallucinated) or No (factual)
                    """,
                    rails=["Yes", "No"],
                    provide_explanation=False
                )
                
                # 결과 파싱
                if len(hallucination_eval) > 0:
                    result = hallucination_eval.iloc[0]
                    is_hallucinated = result.get('label', 'No') == 'Yes'
                    score = 0.2 if is_hallucinated else 0.9
                    label = "hallucinated" if is_hallucinated else "factual"
                    
                    evaluations["hallucination"] = {"score": score, "label": label}
                
            except Exception as e:
                print(f"⚠️ Hallucination llm_classify 실패: {e}")
                # 폴백: 기존 overlap 방식
                evaluations["hallucination"] = self._evaluate_hallucination_fallback(ai_response, search_results)
            
            # 2. QA Correctness 평가  
            try:
                qa_eval = llm_classify(
                    dataframe=eval_df,
                    template="""
Question: {input}
Reference Context: {retrieved_context}
AI Response: {output}

Does the AI response correctly answer the question based on the context?
Answer: Correct or Incorrect
                    """,
                    rails=["Correct", "Incorrect"],
                    provide_explanation=False
                )
                
                if len(qa_eval) > 0:
                    result = qa_eval.iloc[0]
                    is_correct = result.get('label', 'Correct') == 'Correct' 
                    score = 0.9 if is_correct else 0.3
                    label = "correct" if is_correct else "incorrect"
                    
                    evaluations["qa_correctness"] = {"score": score, "label": label}
                    
            except Exception as e:
                print(f"⚠️ QA Correctness llm_classify 실패: {e}")
                # 폴백: 검색 품질 기반
                evaluations["qa_correctness"] = self._evaluate_qa_fallback(search_results)
            
            # 3. Relevance (검색 점수 기반 - 의미있는 지표)
            if search_results:
                relevance_score = search_results[0].score
                evaluations["relevance"] = {
                    "label": "high" if relevance_score > 0.7 else "medium" if relevance_score > 0.4 else "low",
                    "score": float(relevance_score)
                }
                
        except Exception as e:
            print(f"⚠️ llm_classify 전체 실패: {e}")
            raise e  # 상위에서 폴백 처리
            
        return evaluations
    def _evaluate_with_phoenix_official(self, query: str, search_results: List[SearchResult], ai_response: str) -> Dict[str, Any]:
        """🔥 Phoenix 공식 방식 그대로"""
        import pandas as pd
        from phoenix.evals import OpenAIModel, HallucinationEvaluator, QAEvaluator, RelevanceEvaluator, run_evals
        from phoenix.evals import SpanEvaluations, DocumentEvaluations
        import phoenix as px
        
        # 평가 모델
        eval_model = OpenAIModel(model="gpt-4-turbo-preview")
        
        # Evaluators (내장 template 사용)
        hallucination_evaluator = HallucinationEvaluator(eval_model)
        qa_correctness_evaluator = QAEvaluator(eval_model)
        relevance_evaluator = RelevanceEvaluator(eval_model)
        
        # 데이터 준비
        search_content = "\n".join([r.chunk.content for r in search_results[:3]])
        queries_df = pd.DataFrame([{
            'input': query,
            'output': ai_response,
            'reference': search_content
        }])
        
        retrieved_documents_df = pd.DataFrame([
            {'input': query, 'reference': result.chunk.content, 'document_position': i}
            for i, result in enumerate(search_results)
        ])
        
        # 평가 실행
        hallucination_eval_df, qa_correctness_eval_df = run_evals(
            dataframe=queries_df,
            evaluators=[hallucination_evaluator, qa_correctness_evaluator],
            provide_explanation=True,
        )
        
        relevance_eval_df = run_evals(
            dataframe=retrieved_documents_df,
            evaluators=[relevance_evaluator],
            provide_explanation=True,
        )[0]
        
        # 🔥 공식 방식: Phoenix DB에 저장
        px.Client().log_evaluations(
            SpanEvaluations(eval_name="Hallucination", dataframe=hallucination_eval_df),
            SpanEvaluations(eval_name="QA Correctness", dataframe=qa_correctness_eval_df),
        )
        
        px.Client().log_evaluations(
            DocumentEvaluations(eval_name="Relevance", dataframe=relevance_eval_df)
        )
        
        return {"status": "evaluations_logged_to_phoenix"}
    def _calculate_evaluations(self, query: str, search_results: List[SearchResult], ai_response: str = None) -> Dict[str, Any]:
        """평가 지표 계산 - Hallucination, QA Correctness 등"""
        evaluations = {}
        
        # 1. Hallucination 감지 (간단한 휴리스틱)
        if ai_response:
            # AI 응답이 검색 결과와 얼마나 일치하는지
            search_content = " ".join([r.chunk.content for r in search_results[:3]])
            response_words = set(ai_response.lower().split())
            search_words = set(search_content.lower().split())
            overlap_ratio = len(response_words & search_words) / len(response_words) if response_words else 0
            
            if overlap_ratio > 0.3:
                evaluations["hallucination"] = {"label": "factual", "score": 0.85}
            else:
                evaluations["hallucination"] = {"label": "hallucinated", "score": 0.45}
        else:
            evaluations["hallucination"] = {"label": "factual", "score": 0.82}
        
        # 2. QA Correctness (검색 품질 기반)
        if search_results:
            avg_score = sum(r.score for r in search_results) / len(search_results)
            top_score = max(r.score for r in search_results)
            
            if top_score > 0.8 and avg_score > 0.6:
                evaluations["qa_correctness"] = {"label": "correct", "score": 0.91}
            elif top_score > 0.6:
                evaluations["qa_correctness"] = {"label": "correct", "score": 0.75}
            else:
                evaluations["qa_correctness"] = {"label": "incorrect", "score": 0.45}
        else:
            evaluations["qa_correctness"] = {"label": "correct", "score": 0.80}
        
        # 3. Relevance 점수
        if search_results:
            relevance_score = search_results[0].score if search_results else 0.0
            evaluations["relevance"] = {
                "label": "high" if relevance_score > 0.7 else "medium" if relevance_score > 0.4 else "low",
                "score": float(relevance_score)
            }
        
        return evaluations
    
    def _estimate_token_usage(self, input_text: str, output_text: str) -> Dict[str, int]:
        """토큰 사용량 추정 (실제 API 호출 없이)"""
        # 간단한 추정: 영어 4자당 1토큰, 한국어 2자당 1토큰
        input_tokens = len(input_text.encode('utf-8')) // 3
        output_tokens = len(output_text.encode('utf-8')) // 3
        
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens, 
            "total_tokens": input_tokens + output_tokens
        }
    
    def monitor_rag_query(
        self,
        query: str,
        filename: str,
        search_results: List[SearchResult],
        search_time_ms: float = 0,
        ai_response: str = None
    ) -> str:
        """AI 응답이 있을 때 호출 - 완전한 RAG 모니터링"""
        
        if not (self.phoenix_started and self.client):
            return ""
            
        try:
            from opentelemetry import trace
            from phoenix.trace import using_project
            
            session_id = self._get_session_id(filename)
            self.session_cache[filename]['query_count'] += 1
            query_num = self.session_cache[filename]['query_count']
            
            evaluations = self._calculate_evaluations(query, search_results, ai_response)
            
            with using_project(self.project_name):
                tracer = trace.get_tracer(__name__)
                
                # LLM span (AI 응답 포함)
                with tracer.start_as_current_span("query") as main_span:
                    main_span.set_attribute("openinference.span.kind", "LLM")
                    main_span.set_attribute("input.value", query)
                    main_span.set_attribute("output.value", ai_response)
                    
                    # 토큰 정보
                    tokens = self._estimate_token_usage(query, ai_response)
                    main_span.set_attribute("llm.token_count.total", tokens["total_tokens"])
                    main_span.set_attribute("llm.search_time_ms", search_time_ms)
                    
                    # Evaluations
                    for eval_name, eval_data in evaluations.items():
                        main_span.set_attribute(f"evaluation.{eval_name}.label", eval_data["label"])
                        main_span.set_attribute(f"evaluation.{eval_name}.score", eval_data["score"])
                
                print(f"📊 RAG Query 완료: Q{query_num}")
                return session_id
                
        except Exception as e:
            print(f"⚠️ RAG Query 에러: {e}")
            return ""
    
    def monitor_search_results(
        self,
        query: str,
        filename: str,
        search_results: List[SearchResult],
        search_time_ms: float = 0,        
        method: str = "retrieve"
    ) -> str:
        """검색 결과만 있을 때 호출 - Retriever span들만 생성"""
        
        if not (self.phoenix_started and self.client and search_results):
            return ""
            
        try:
            from opentelemetry import trace
            from phoenix.trace import using_project
            from openinference.semconv.trace import (
                SpanAttributes,
                OpenInferenceSpanKindValues,
                DocumentAttributes
            )
            
            session_id = self._get_session_id(filename)
            self.session_cache[filename]['query_count'] += 1
            query_num = self.session_cache[filename]['query_count']
            
            with using_project(self.project_name):
                tracer = trace.get_tracer(__name__)
                start_ns = time.time_ns()
                end_ns   = start_ns + int(search_time_ms * 1e6)  # ms → ns 변환
                
                # Retriever spans만 생성
                for i, result in enumerate(search_results):
                    # with tracer.start_as_current_span("retrieve") as chunk_span:
                    # 2) span 생성 (start_time 지정)
                    with tracer.start_as_current_span(
                        method,
                        start_time=start_ns,
                        attributes={
                            SpanAttributes.OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.RETRIEVER.value,
                            SpanAttributes.INPUT_VALUE:             f"{query} | Rank #{i+1}"
                        }
                    ) as chunk_span:
                        # 3) 출력값 (문서 내용)
                        chunk_span.set_attribute(SpanAttributes.OUTPUT_VALUE, result.chunk.content)

                        # 4) 문서 점수 (semantic key 사용)
                        chunk_span.set_attribute(
                            DocumentAttributes.DOCUMENT_SCORE, 
                            float(result.score)
                        )

                        # 5) 검색 시간(ms) 커스텀 속성
                        chunk_span.set_attribute(
                            "retrieval.search_time_ms", 
                            search_time_ms
                        )

                        # 6) 세션·메타데이터
                        chunk_span.set_attribute("session.session_id", session_id)
                        chunk_span.set_attribute("metadata.filename", filename)
                        chunk_span.set_attribute("metadata.chunk_rank", i + 1)
                        # chunk_span.set_attribute("chunk_rank", i + 1) #커스텀/미등록 키를 “Metadata” 카테고리로 어차피 자동 분류합니다
                        chunk_span.set_attribute("metadata.query_number", query_num)

                        # 7) BBox 예시
                        chunk_span.set_attribute(
                            "metadata.bbox",
                            str([0.6172452489318663, 0.9592069953131686, 
                                0.9021840911883696, 0.9693693880041185])
                        )

                        # 8) Relevance 평가
                        rel_score = float(result.score)
                        rel_label = ("high" if rel_score > 0.7 
                                    else "medium" if rel_score > 0.4 
                                    else "low")
                        chunk_span.set_attribute("evaluation.relevance.score", rel_score)
                        chunk_span.set_attribute("evaluation.relevance.label", rel_label)

                    # 9) span 강제 종료 (end_time 지정)
                    chunk_span.end(end_time=end_ns)
                
                print(f"📊 Search Results 완료: Q{query_num}, {len(search_results)}개 결과")
                return session_id
                
        except Exception as e:
            print(f"⚠️ Search Results 에러: {e}")
            return ""
    
    def update_with_ai_response(
        self,
        session_id: str,
        query: str,
        ai_response: str,
        actual_token_usage: Dict[str, int] = None
    ):
        """🔄 AI 응답 완료 후 업데이트 (향후 확장용)"""
        # 캐시에 저장해서 다음 모니터링 시 활용
        self.ai_response_cache[session_id] = {
            'query': query,
            'response': ai_response,
            'tokens': actual_token_usage,
            'timestamp': datetime.now()
        }
        print(f"💾 AI 응답 캐시됨: {session_id}")


# === 싱글톤 인스턴스 ===
_phoenix_monitor_instance: PhoenixRAGMonitor = None

def get_phoenix_monitor() -> PhoenixRAGMonitor:
    """Phoenix 모니터 인스턴스 반환"""
    global _phoenix_monitor_instance
    if _phoenix_monitor_instance is None:
        _phoenix_monitor_instance = PhoenixRAGMonitor()
    return _phoenix_monitor_instance


# === 외부 호출 함수 ===
def auto_monitor_chat(
    query: str,
    filename: str,
    search_results: List[SearchResult],
    search_time_ms: float = 0,
    ai_response: str = None,
    method: str = "retrieve"
) -> str:
    """chat-with-pdf에서 호출하는 통합 모니터링"""
    monitor = get_phoenix_monitor()
    
    if ai_response:
        # AI 응답이 있으면 완전한 RAG 모니터링
        return monitor.monitor_rag_query(
            query=query,
            filename=filename,
            search_results=search_results,
            search_time_ms=search_time_ms,
            ai_response=ai_response
        )
    else:
        # 검색 결과만 있으면 Retriever span만 생성
        return monitor.monitor_search_results(
            query=query,
            filename=filename,
            search_results=search_results,
            search_time_ms=search_time_ms,
            method = method
        )