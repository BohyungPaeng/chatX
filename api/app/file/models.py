from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from ..chat.models import ChatMessage


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