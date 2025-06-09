from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any, Literal
import warnings
warnings.filterwarnings("ignore", message=".*has conflict with protected namespace.*")


class ChatMessage(BaseModel):
    role: str = "user"
    content: str


class ImageAnalysisRequest(BaseModel):
    """이미지 분석 요청 모델"""
    
    # Pydantic 경고 억제
    model_config = {'protected_namespaces': ()}
    
    image_url: Optional[str] = None
    prompt: str
    system_prompt: Optional[str] = None  # 새로 추가
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

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1000
    stream: bool = False
    enable_web_search: Optional[bool] = False
    search_query: Optional[str] = None
    # 파일 분석 지원 (기존 Image 모델로 통합)
    file_analysis: Optional[bool] = False
    file_data: Optional[str] = None  # base64 파일 데이터


class ChatResponse(BaseModel):
    response: str
    model: str
    usage: dict
    is_streaming: Optional[bool] = False
    citations: Optional[List[Dict[str, str]]] = None


class WebSearchRequest(BaseModel):
    query: str
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1000
    search_context_size: Optional[str] = "medium"  # low, medium, high 중 하나
    # 예제 user_location:
    # {
    #   "country": "KR",
    #   "city": "Seoul",
    #   "region": "Seoul",
    #   "timezone": "Asia/Seoul"
    # }
    user_location: Optional[Dict[str, str]] = None


class WebSearchResponse(BaseModel):
    response: str
    model: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    citations: Optional[List[Dict[str, Union[str, int]]]] = None