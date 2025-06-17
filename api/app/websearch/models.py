from pydantic import BaseModel
from typing import Optional, Dict, List, Union, Any


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