from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any, Literal
from fastapi import UploadFile


class ChatMessage(BaseModel):
    role: str = "user"
    content: str


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


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1000
    stream: bool = False
    enable_web_search: Optional[bool] = False
    search_query: Optional[str] = None


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


# 파일 업로드 및 검색 관련 모델 추가
class FileUploadResponse(BaseModel):
    """파일 업로드 응답 모델"""
    success: bool
    file_id: Optional[str] = None
    vector_store_id: Optional[str] = None
    error: Optional[str] = None


class FileAnnotation(BaseModel):
    """파일 인용 정보 모델"""
    type: str
    index: int
    file_id: str
    filename: str
    quote: Optional[str] = None  # 실제 인용된 텍스트
    page: Optional[int] = None   # 페이지 번호 (가능한 경우)
    score: Optional[float] = None  # 검색 점수 (가능한 경우)


class FileSearchResult(BaseModel):
    """파일 검색 결과 모델"""
    file_id: str
    text: str
    score: float
    object_type: str = "file_search_result"


class FileQueryRequest(BaseModel):
    """파일 질의 요청 모델"""
    query: str
    vector_store_id: str  # 현재는 file_id로 사용됩니다
    conversation_history: Optional[List[ChatMessage]] = None  # 대화 히스토리 추가
    model: Optional[str] = None  # 사용할 모델 추가


class FileQueryResponse(BaseModel):
    """파일 질의 응답 모델"""
    response: str
    annotations: Optional[List[FileAnnotation]] = []
    search_results: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


# 다중 파일 업로드를 위한 새로운 모델들
class FileUploadResult(BaseModel):
    """개별 파일 업로드 결과"""
    filename: str
    success: bool
    file_id: Optional[str] = None
    error: Optional[str] = None


class MultiFileUploadResponse(BaseModel):
    """다중 파일 업로드 응답 모델"""
    success: bool
    vector_store_id: Optional[str] = None
    results: List[FileUploadResult] = []
    error: Optional[str] = None 