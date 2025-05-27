# api/app/image_flow.py

import time
from typing import Any, Dict
from pocketflow import AsyncNode, AsyncFlow  # PocketFlow 비동기 노드·플로우 :contentReference[oaicite:0]{index=0}
from .pwc_gpt import AsyncPwCGPTModel  # PWC GPT 모델 래퍼 :contentReference[oaicite:1]{index=1}

class ImageAnalysisNode(AsyncNode):
    """
    이미지를 분석하기 위해 PWC GPT 모델을 호출하는 노드.
    shared 에서 image_url, prompt, max_tokens 를 받아 run 결과를 shared['analysis_result'] 에 저장합니다.
    """
    def __init__(self, model: AsyncPwCGPTModel):
        super().__init__()
        self.model = model

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "image_url": shared.get("image_url"),
            "prompt": shared.get("prompt", ""),
            "max_tokens": shared.get("max_tokens", 500)
        }

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        system_msg = {"role": "system", "content": "You are an expert image analysis assistant. Describe the image in detail."}
        user_msg = {
            "role": "user",
            "content": f"{prep_res['prompt']}\nImage URL: {prep_res['image_url']}"
        }
        start = time.time()
        result = await self.model.run(
            [system_msg, user_msg],
            max_tokens=prep_res["max_tokens"]
        )
        elapsed = time.time() - start
        return {"analysis": result, "elapsed": elapsed}

    async def post_async(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> Any:
        shared["analysis_result"] = exec_res["analysis"]
        shared["analysis_elapsed"] = exec_res["elapsed"]
        return None  # 흐름 종료

def create_image_analysis_flow(model: AsyncPwCGPTModel) -> AsyncFlow:
    """
    ImageAnalysisNode 하나로만 구성된 간단한 AsyncFlow 생성.
    """
    node = ImageAnalysisNode(model)
    return AsyncFlow(start=node)
