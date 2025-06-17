from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from .models import WebSearchRequest, WebSearchResponse
from .services import perform_web_search

router = APIRouter()


@router.post("/websearch", response_model=WebSearchResponse)
async def web_search(request: WebSearchRequest):
    """
    OpenAI API의 웹 검색 도구를 사용하여 웹 검색을 수행합니다.
    
    Args:
        request: 웹 검색 요청 데이터
    
    Returns:
        WebSearchResponse: 웹 검색 결과
    """
    try:
        response = await perform_web_search(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/websearch", response_model=WebSearchResponse)
async def web_search_get(
    query: str = Query(..., description="검색 쿼리"),
    model: Optional[str] = Query("gpt-4.1", description="사용할 모델"),
    search_context_size: str = Query("medium", description="검색 컨텍스트 크기 (low/medium/high)")
):
    """
    OpenAI API의 웹 검색 도구를 사용하여 웹 검색을 수행합니다. (GET 메서드)
    
    Args:
        query: 검색 쿼리
        model: 사용할 모델 ID
        search_context_size: 검색 컨텍스트 크기
    
    Returns:
        WebSearchResponse: 웹 검색 결과
    """
    request = WebSearchRequest(
        query=query,
        model=model,
        search_context_size=search_context_size
    )
    
    try:
        response = await perform_web_search(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))