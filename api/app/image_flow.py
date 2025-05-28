# api/app/image_flow.py

import time
from typing import Any, Dict
from pocketflow import AsyncNode, AsyncFlow  # PocketFlow 비동기 노드·플로우 :contentReference[oaicite:0]{index=0}
from .pwc_gpt import AsyncPwCGPTModel  # PWC GPT 모델 래퍼 :contentReference[oaicite:1]{index=1}

class ImageAnalysisNode(AsyncNode):
    """
    이미지를 분석하기 위해 PWC GPT 모델을 호출하는 노드.
    """
    def __init__(self, model: AsyncPwCGPTModel):
        super().__init__()
        self.model = model

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        # 기본 시스템 프롬프트 (OCR용이 아닌 일반적인 이미지 분석 )
        default_system_prompt = "You are an expert image analysis assistant. Analyze the image accurately and provide helpful insights."
        
        return {
            "image_url": shared.get("image_url"),
            "user_prompt": shared.get("prompt", ""),
            "system_prompt": shared.get("system_prompt", default_system_prompt),
            "max_tokens": shared.get("max_tokens", 500)
        }

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:

        # print(f"[TEMP DEBUG] prep_res: {prep_res}")
        messages = [
            {"role": "system", "content": prep_res['system_prompt']},
            {
                "role": "user", 
                "content": [
                    {"type": "text", "text": prep_res['user_prompt']},
                    {"type": "image_url", "image_url": {"url": prep_res['image_url']}}
                ]
            }
        ]
        
        start = time.time()
        try:
            result = await self.model.run(
                messages=messages,
                max_tokens=prep_res["max_tokens"]
            )
            elapsed = time.time() - start
            print(f"PWC GPT Analysis completed in {elapsed:.2f}s")
            return {"analysis": result, "elapsed": elapsed}
        except Exception as e:
            elapsed = time.time() - start
            print(f"PWC GPT Analysis failed after {elapsed:.2f}s: {str(e)}")
            return {"analysis": f"PWC GPT 분석 실패: {str(e)}", "elapsed": elapsed}

    async def post_async(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> Any:
        shared["analysis_result"] = exec_res["analysis"]
        shared["analysis_elapsed"] = exec_res["elapsed"]
        return None
    
def create_image_analysis_flow(model: AsyncPwCGPTModel) -> AsyncFlow:
    """
    ImageAnalysisNode 하나로만 구성된 간단한 AsyncFlow 생성.
    """
    node = ImageAnalysisNode(model)
    return AsyncFlow(start=node)
