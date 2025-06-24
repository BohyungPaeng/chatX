from pydantic import BaseModel
from typing import List, Optional
from ..chat.models import ChatMessage


class ImageAnalysisRequest(BaseModel):
    """
    이미지 분석 요청 모델
    """
    image_url: Optional[str] = None
    prompt: str
    model: Optional[str] = None
    max_tokens: int = 1000
    detail: str = "auto"
    stream: bool = False
    conversation_history: Optional[List[ChatMessage]] = None


class ImageAnalysisResponse(BaseModel):
    response: str
    model: str
    usage: dict

""" 이미지 생성 모델 API의 프론트 반환서식. 초기버전은 b64 압축하여"""
class ImageGenResponse(BaseModel):
    b64: str