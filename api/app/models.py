from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any, Literal


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


class FileAnalysisRequest(BaseModel):
    """
    파일 분석 요청 모델
    """
    file_content: bytes = Field(..., description="파일 내용 (바이트)")
    file_type: Literal["image", "pdf"] = Field(..., description="파일 타입")
    prompt: str = Field(default="이 파일에 대해 설명해주세요.", description="분석 프롬프트")
    model: Optional[str] = Field(default="gpt-4.1", description="사용할 AI 모델")
    max_tokens: int = Field(default=1000, description="최대 토큰 수")
    stream: bool = Field(default=False, description="스트리밍 응답 여부")

class FileAnalysisResponse(BaseModel):
    """
    파일 분석 응답 모델
    """
    response: str = Field(..., description="AI 분석 결과")
    model: str = Field(..., description="사용된 모델명")
    file_type: str = Field(..., description="분석된 파일 타입")
    usage: Dict[str, Any] = Field(..., description="토큰 사용량 정보")
    preview_url: Optional[str] = Field(None, description="파일 미리보기 URL (base64)")

class FileUploadMetadata(BaseModel):
    """
    파일 업로드 메타데이터
    """
    filename: str = Field(..., description="파일명")
    content_type: str = Field(..., description="MIME 타입")
    file_size: int = Field(..., description="파일 크기 (바이트)")
    file_type: Literal["image", "pdf", "unknown"] = Field(..., description="감지된 파일 타입")

class ProcessedFileInfo(BaseModel):
    """
    처리된 파일 정보
    """
    original_filename: str = Field(..., description="원본 파일명")
    file_type: str = Field(..., description="파일 타입")
    file_size_mb: float = Field(..., description="파일 크기 (MB)")
    preview_generated: bool = Field(..., description="미리보기 생성 여부")
    processing_time_ms: int = Field(..., description="처리 시간 (밀리초)")

# 기존 모델들과 통합을 위한 확장
class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1000
    stream: bool = False
    enable_web_search: Optional[bool] = False
    search_query: Optional[str] = None
    # 🔧 추가: 파일 분석 지원
    file_analysis: Optional[bool] = False
    file_data: Optional[str] = None  # base64 파일 데이터

class ChatResponse(BaseModel):
    response: str
    model: str
    usage: dict
    is_streaming: Optional[bool] = False
    citations: Optional[List[Dict[str, str]]] = None
    # 🔧 추가: 파일 분석 결과
    file_info: Optional[ProcessedFileInfo] = None


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