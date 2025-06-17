import openai
import httpx
import ssl

from ..core.config import OPENAI_API_KEY
from .models import WebSearchRequest, WebSearchResponse

# SSL 인증서 검증 비활성화
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# OpenAI 클라이언트 설정
client = openai.OpenAI(
    api_key=OPENAI_API_KEY,
    http_client=httpx.Client(verify=False),
    max_retries=3,
    timeout=60.0
)


async def perform_web_search(request: WebSearchRequest) -> WebSearchResponse:
    """
    OpenAI API의 웹 검색 도구를 사용하여 웹 검색을 수행합니다.
    
    Args:
        request: WebSearchRequest 모델의 요청 데이터
    
    Returns:
        WebSearchResponse: 웹 검색 결과
    """
    try:
        # 모델 설정 - 웹 검색 지원 모델 사용
        # 요청된 모델이 있으면 사용하되, 웹 검색을 지원하지 않는 모델이면 기본 모델 사용
        requested_model = request.model or "gpt-4o-search-preview"
        
        # 웹 검색 지원 모델 목록
        web_search_models = ["gpt-4o-search-preview", "gpt-4o"]
        
        if requested_model in web_search_models:
            model = requested_model
        elif requested_model.startswith("gpt-4"):
            model = "gpt-4o-search-preview"  # GPT-4 계열이면 검색 지원 모델 사용
        else:
            model = "gpt-4o-search-preview"  # 기본값
        
        print(f"웹 검색 모델: 요청={requested_model}, 사용={model}")

        # API 호출 준비
        messages = [
            {
                "role": "user",
                "content": request.query
            }
        ]

        # API 호출 - 웹 검색 지원 모델은 web_search_options 파라미터 없이도 자동으로 웹 검색 수행
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=request.max_tokens
        )
        
        # 응답 파싱
        content = response.choices[0].message.content
        
        # 인용 정보 추출
        citations = []
        # API 응답 로깅하여 디버깅
        print(f"Web search response structure: {type(response.choices[0].message)}")
        if hasattr(response.choices[0].message, 'annotations'):
            annotations = response.choices[0].message.annotations
            print(f"Annotations type: {type(annotations)}")
            
            # annotations가 리스트인 경우
            if isinstance(annotations, list):
                for annotation in annotations:
                    # 객체인 경우
                    if hasattr(annotation, 'type'):
                        if annotation.type == 'url_citation':
                            citations.append({
                                'url': annotation.url_citation.url,
                                'title': annotation.url_citation.title,
                                'start_index': annotation.url_citation.start_index,
                                'end_index': annotation.url_citation.end_index
                            })
                    # 딕셔너리인 경우
                    elif isinstance(annotation, dict) and 'type' in annotation:
                        if annotation['type'] == 'url_citation':
                            url_citation = annotation['url_citation']
                            citations.append({
                                'url': url_citation['url'],
                                'title': url_citation['title'],
                                'start_index': url_citation['start_index'],
                                'end_index': url_citation['end_index']
                            })
        # 사용량 정보
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }
        
        return WebSearchResponse(
            response=content,
            model=model,
            usage=usage,
            citations=citations
        )
    
    except Exception as e:
        # 에러 처리
        error_message = f"Error performing web search: {str(e)}"
        print(f"Web search error: {str(e)}")
        return WebSearchResponse(
            response=error_message,
            model=model,
            usage={"error": str(e)}
        )