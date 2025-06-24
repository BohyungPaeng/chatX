# api/app/rag_dashboard_gradio.py
"""
Gradio 기반 RAG 대시보드 - 원하는 모든 기능 구현
"""
import gradio as gr
import pandas as pd
import plotly.express as px
from datetime import datetime
import json
import time
from .rag_engine import search_with_faiss_engine

class GradioRAGDashboard:
    def __init__(self):
        self.search_history = []
        self.app = self._create_dashboard()
        
    def _create_dashboard(self):
        """커스텀 대시보드 생성"""
        
        def search_and_display(query, search_results, search_time_ms):
            # 결과를 DataFrame으로 변환
            data = []
            for i, result in enumerate(search_results):
                data.append({
                    "순위": i + 1,
                    "점수": f"{result.score:.4f}",
                    "페이지": result.chunk.page_number,
                    "내용 미리보기": result.chunk.content[:100] + "...",
                    "전체 내용": result.chunk.content,
                    "Citation": result.citation
                })
            
            df = pd.DataFrame(data)
            
            # 통계 계산
            scores = [r.score for r in search_results]
            stats = {
                "평균 점수": f"{sum(scores)/len(scores):.4f}",
                "최고 점수": f"{max(scores):.4f}",
                "최저 점수": f"{min(scores):.4f}",
                "검색 시간": f"{search_time_ms:.2f}ms",
                "결과 수": len(search_results)
            }
            
            # 점수 분포 차트
            fig = px.bar(
                x=list(range(1, len(scores)+1)),
                y=scores,
                labels={'x': 'Rank', 'y': 'Score'},
                title='검색 결과 점수 분포'
            )
            
            # 히스토리 저장
            self.search_history.append({
                "time": datetime.now(),
                "query": query,
                "results": len(search_results),
                "avg_score": sum(scores)/len(scores)
            })
            
            # 상세 정보 HTML
            details_html = "<div style='max-height: 400px; overflow-y: auto;'>"
            for i, result in enumerate(search_results):
                color = "green" if result.score > 0.8 else "orange" if result.score > 0.5 else "red"
                details_html += f"""
                <div style='border: 2px solid {color}; margin: 10px; padding: 10px; border-radius: 5px;'>
                    <h4>{result.citation} - Score: {result.score:.4f}</h4>
                    <pre style='white-space: pre-wrap;'>{result.chunk.content}</pre>
                    <small>Page: {result.chunk.page_number} | Length: {len(result.chunk.content)} chars</small>
                </div>
                """
            details_html += "</div>"
            
            return df, json.dumps(stats, indent=2, ensure_ascii=False), fig, details_html
        
        # Gradio 인터페이스
        with gr.Blocks(title="ChatX RAG Monitor") as app:
            gr.Markdown("# 🔍 ChatX RAG 성능 모니터링 대시보드")
            
            with gr.Row():
                query_input = gr.Textbox(label="검색 쿼리", placeholder="질문을 입력하세요...")
                top_k_slider = gr.Slider(1, 20, 5, label="Top-K", step=1)
                search_btn = gr.Button("🔍 검색", variant="primary")
            
            with gr.Tabs():
                with gr.Tab("📊 결과 테이블"):
                    results_table = gr.DataFrame(
                        headers=["순위", "점수", "페이지", "내용 미리보기"],
                        label="검색 결과"
                    )
                
                with gr.Tab("📈 통계 & 차트"):
                    with gr.Row():
                        stats_display = gr.JSON(label="통계 정보")
                        score_chart = gr.Plot(label="점수 분포")
                
                with gr.Tab("📄 상세 내용"):
                    details_display = gr.HTML(label="청크 상세 정보")
            
            # 이벤트 연결
            search_btn.click(
                search_and_display,
                inputs=[query_input, top_k_slider],
                outputs=[results_table, stats_display, score_chart, details_display]
            )
        
        return app
    
    def launch(self):
        """대시보드 실행"""
        self.app.launch(server_name="0.0.0.0", server_port=7860, share=False)

# 사용법
if __name__ == "__main__":
    dashboard = GradioRAGDashboard()
    dashboard.launch()
    print("🎯 Gradio 대시보드: http://localhost:7860")