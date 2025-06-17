import openai
import json
import asyncio
import httpx
import ssl
from fastapi.responses import StreamingResponse

from ..core.config import OPENAI_API_KEY
from .models import ImageAnalysisRequest, ImageAnalysisResponse

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


async def analyze_image(request: ImageAnalysisRequest) -> ImageAnalysisResponse:
    """
    OpenAI API를 사용하여 이미지를 분석합니다.
    
    Args:
        request: ImageAnalysisRequest 모델의 요청 데이터
    
    Returns:
        ImageAnalysisResponse: 이미지 분석 결과
    """
    try:
        # 모델 설정 (기본값: GPT-4 Vision)
        model = request.model or "gpt-4.1"
        
        # 이미지 URL 확인 및 처리
        image_url = request.image_url
        
        if not image_url:
            raise ValueError("유효한 이미지 URL이 필요합니다.")
        
        # API 호출을 위한 입력 구성
        messages = []
        
        # 대화 컨텍스트가 있으면 추가
        if request.conversation_history:
            for msg in request.conversation_history:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # 사용자 메시지와 이미지 추가
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": request.prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url
                    }
                }
            ]
        })
        
        # API 호출
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=request.max_tokens
        )
        
        # 응답 파싱
        content = response.choices[0].message.content
        
        # 사용량 정보
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }
        
        return ImageAnalysisResponse(
            response=content,
            model=model,
            usage=usage
        )
        
    except Exception as e:
        # 에러 처리
        error_message = f"Error analyzing image: {str(e)}"
        print(f"Image analysis error: {str(e)}")
        return ImageAnalysisResponse(
            response=error_message,
            model=model or "gpt-4.1",
            usage={"error": str(e)}
        )


async def analyze_image_streaming(request: ImageAnalysisRequest):
    """
    이미지를 분석하고 스트리밍 응답을 생성합니다.
    
    Args:
        request: ImageAnalysisRequest 객체
        
    Returns:
        StreamingResponse: 스트리밍 응답 객체
    """
    # 모델 설정 (기본값: GPT-4 Vision)
    model = request.model or "gpt-4.1"
    
    async def stream_generator():
        try:
            # 이미지 URL 확인 및 처리
            image_url = request.image_url
            
            if not image_url:
                raise ValueError("유효한 이미지 URL이 필요합니다.")
            
            # API 호출을 위한 입력 구성
            messages = []
            
            # 대화 컨텍스트가 있으면 추가
            if request.conversation_history:
                for msg in request.conversation_history:
                    messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
            
            # 사용자 메시지와 이미지 추가
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": request.prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            })
            
            # API 호출
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=request.max_tokens,
                stream=True
            )
            
            collected_messages = []
            
            # 청크 스트리밍
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    collected_messages.append(content)
                    
                    # 각 청크를 JSON으로 반환
                    yield f"data: {json.dumps({'content': content, 'is_streaming': True, 'model': model})}\n\n"
                    await asyncio.sleep(0)
            
            # 스트리밍 완료 신호
            completion_info = {
                'content': '', 
                'is_streaming': False, 
                'model': model, 
                'usage': {'completion_tokens': len(collected_messages)}
            }
            
            yield f"data: {json.dumps(completion_info)}\n\n"
            yield f"data: [DONE]\n\n"
            
        except Exception as e:
            # 에러 처리
            error_message = f"Error streaming image analysis: {str(e)}"
            print(f"Image streaming error: {str(e)}")
            yield f"data: {json.dumps({'content': error_message, 'is_streaming': False, 'error': str(e), 'model': model})}\n\n"
            yield f"data: [DONE]\n\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )