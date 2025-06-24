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


async def _get_pwc_model(model_name: str) -> 'AsyncPwCGPTModel':
    """PWC GPT 모델 인스턴스를 생성하고 헬스체크를 수행합니다."""
    from ..tools.pwc_gpt import AsyncPwCGPTModel
    
    pwc = AsyncPwCGPTModel(default_model_name=model_name)
    status = await pwc.health_check()
    if status != 200:
        print(f"PWC GPT health check failed: {status}")
    return pwc

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
        if model.startswith("azure."):
            # PWC GPT 사용
            from .image_flow import create_image_analysis_flow
            
            print(f"Using PWC GPT for model: {model}")
            pwc = await _get_pwc_model(model)
            
            # Flow 실행
            flow = create_image_analysis_flow(pwc)
            shared = {
                "image_url": request.image_url,
                "prompt": request.prompt or "이 이미지에 대해 자세히 설명해주세요.",
                "max_tokens": request.max_tokens
            }
            
            await flow.run_async(shared)
            
            content = shared.get("analysis_result", "PWC GPT 분석 결과가 없습니다.")
            usage = {"elapsed": shared.get("analysis_elapsed", 0)}
        else:
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
            
            collected_messages = []
            if model.startswith("azure."):
                # PWC GPT 스트리밍
                print(f"Using PWC GPT streaming for model: {model}")
                pwc = await _get_pwc_model(model)
                
                # PWC GPT 스트리밍 호출 (OpenAI와 동일한 패턴)
                async for chunk in pwc.run_stream(
                    messages=messages,
                    max_tokens=request.max_tokens,
                    model=model
                ):
                    if "choices" in chunk and len(chunk["choices"]) > 0:
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            collected_messages.append(content)
                            yield f"data: {json.dumps({'content': content, 'is_streaming': True, 'model': model})}\n\n"
                            await asyncio.sleep(0)
                
            else:
            
                # API 호출
                stream = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=request.max_tokens,
                    stream=True
                )
                
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

async def generate_image(title : str):
    """ PWCGPT - IMAGE GENEATION, Not encapsulated YET... """
    from ..config import LITELLM_KEY, LITELLM_URL, IMAGE_GEN_MODEL, PROMPT_BANK

    url = LITELLM_URL + "/images/generations"
    prompts = PROMPT_BANK["imagegen"]
    selected_theme = __import__("random").choice(prompts["themes"]) #FIXME: 또는 키워드기반 함수생성
    if IMAGE_GEN_MODEL.startswith("azure.") or IMAGE_GEN_MODEL.startswith("vertex_ai.") :
        import requests
        headers = {
            "User-Agent": "curl/8.9.1",
            "accept": "application/json",
            "accept-encoding": "gzip, deflate, br",
            "Authorization": "Bearer " + LITELLM_KEY,
            "Content-Type": "application/json", 
            "Connection": "keep-alive",  
            "x-request-type": "sync",
        }

        body = {
            "prompt" : prompts["tmp_assistant"].format(theme =selected_theme, title=title),
            "model": IMAGE_GEN_MODEL,
            "n": 1,
            "quality": "standard",
            "response_format": "url",
            # "size": "1024x1024",
            # "size": "1408x768",
            # "style": "vivid",
            "aspect_ratio": "16:9",
            # "negative_prompt": "realistic human faces, gore, hate symbols",
        }
        response = requests.post(
            url,
            headers=headers, 
            json=body, 
            verify=False,
            allow_redirects=True
        )

        raw_b64 = response.json()['data'][0]['b64_json']
    else:
        # OpenAI DALL-E 사용 (services.py의 client 활용)
        from .services import client
        if IMAGE_GEN_MODEL == "dall-e-2":
            dalle_response = client.images.generate(
                model="dall-e-2", 
                prompt=prompts["tmp_assitant_e2"].format(theme =selected_theme, title=title),
                size="256x256",  # 🔥 1024x1024 → 256x256 (직접 원하는 사이즈)
                n=1,
                response_format="b64_json"
            )
        elif IMAGE_GEN_MODEL == "dall-e-3":
            dalle_response = client.images.generate(
                model="dall-e-3",
                prompt=prompts["tmp_assistant"].format(theme =selected_theme, title=title),
                quality="standard",
                n=1,
                # size="1024x1024",
                response_format="b64_json"
            )
        raw_b64 = dalle_response.data[0].b64_json
        
        # 이미지 URL에서 다운로드 후 base64 변환
        # image_url = dalle_response.data[0].url
        # img_response = requests.get(image_url)
        # img_response.raise_for_status()
        
        # raw_b64 = base64.b64encode(img_response.content).decode("utf-8")
    return raw_b64


