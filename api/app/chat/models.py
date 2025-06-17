from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class ChatMessage(BaseModel):
    role: str = "user"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    user_email: Optional[str] = None  # 👤 사용자 이메일 (SSO 구현 전까지 선택사항)
    conversation_id: Optional[int] = None  # 💬 기존 대화방 ID (새 대화면 None)
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
    conversation_id: Optional[int] = None  # 💬 대화방 ID
    message_id: Optional[int] = None  # 📝 메시지 ID
    is_streaming: Optional[bool] = False
    citations: Optional[List[Dict[str, str]]] = None