import openai
from .config import OPENAI_API_KEY, GPT_MODEL
from .models import ChatMessage, ChatRequest, ChatResponse, ImageAnalysisRequest, ImageAnalysisResponse, WebSearchRequest, WebSearchResponse
from fastapi.responses import StreamingResponse
import json
import asyncio

# OpenAI 클라이언트 설정
client = openai.OpenAI(api_key=OPENAI_API_KEY)
# api/app/services.py에 추가할 함수들

import io
import base64
from PIL import Image
import fitz  # PyMuPDF for PDF processing
from fastapi import HTTPException, UploadFile
from .models import FileAnalysisRequest, FileAnalysisResponse

async def process_uploaded_file(
    file: UploadFile,
    prompt: str = "이 파일에 대해 설명해주세요.",
    model: str = "gpt-4.1",
    max_tokens: int = 1000,
    stream: bool = False
) -> FileAnalysisResponse:
    """
    업로드된 파일(이미지/PDF)을 처리하고 AI 분석을 수행합니다.
    
    Args:
        file: 업로드된 파일 (이미지 또는 PDF)
        prompt: 분석을 위한 프롬프트
        model: 사용할 AI 모델
        max_tokens: 최대 토큰 수
        stream: 스트리밍 응답 여부
    
    Returns:
        FileAnalysisResponse: 파일 분석 결과
    """
    try:
        # 1. 파일 타입 검증
        file_type = detect_file_type(file)
        if file_type not in ["image", "pdf"]:
            raise HTTPException(
                status_code=400, 
                detail="지원되지 않는 파일 형식입니다. 이미지 또는 PDF만 지원합니다."
            )
        
        # 2. 파일 크기 검증
        await validate_file_size(file, max_size_mb=25)
        
        # 3. 파일 내용 읽기
        file_content = await file.read()
        
        # 4. 파일 처리 및 base64 변환
        if file_type == "pdf":
            base64_data = await process_pdf_to_base64(file_content)
        else:  # image
            base64_data = await process_image_to_base64(file_content)
        
        # 5. AI 분석 요청 생성
        analysis_request = create_ai_analysis_request(
            base64_data=base64_data,
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            file_type=file_type
        )
        
        # 6. AI API 호출
        if stream:
            return await analyze_file_streaming(analysis_request)
        else:
            return await analyze_file_standard(analysis_request)
            
    except Exception as e:
        print(f"File processing error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"파일 처리 중 오류가 발생했습니다: {str(e)}"
        )

def detect_file_type(file: UploadFile) -> str:
    """
    파일 타입을 감지합니다.
    
    Args:
        file: 업로드된 파일
    
    Returns:
        str: "image", "pdf", 또는 "unknown"
    """
    content_type = file.content_type or ""
    filename = file.filename or ""
    
    # MIME 타입으로 먼저 확인
    if content_type.startswith("image/"):
        return "image"
    elif content_type == "application/pdf":
        return "pdf"
    
    # 파일 확장자로 확인
    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
        return "image"
    elif filename.lower().endswith('.pdf'):
        return "pdf"
    
    return "unknown"

async def validate_file_size(file: UploadFile, max_size_mb: int = 25):
    """
    파일 크기를 검증합니다.
    
    Args:
        file: 업로드된 파일
        max_size_mb: 최대 허용 크기 (MB)
    
    Raises:
        HTTPException: 파일 크기가 초과된 경우
    """
    # 파일 크기 확인을 위해 seek/tell 사용
    file.file.seek(0, 2)  # 파일 끝으로 이동
    size = file.file.tell()  # 현재 위치 = 파일 크기
    file.file.seek(0)  # 파일 시작으로 되돌리기
    
    max_size_bytes = max_size_mb * 1024 * 1024
    if size > max_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"파일 크기가 너무 큽니다. 최대 {max_size_mb}MB까지 지원합니다."
        )

async def process_pdf_to_base64(pdf_content: bytes) -> str:
    """
    PDF 파일을 처리하여 첫 번째 페이지를 이미지로 변환하고 base64로 인코딩합니다.
    
    Args:
        pdf_content: PDF 파일 바이트 내용
    
    Returns:
        str: base64 인코딩된 이미지 데이터 (data URL 형식)
    """
    try:
        # PyMuPDF를 사용하여 PDF 열기
        pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
        
        if len(pdf_document) == 0:
            raise ValueError("PDF 파일이 비어있습니다.")
        
        # 첫 번째 페이지 가져오기
        first_page = pdf_document[0]
        
        # 페이지를 이미지로 변환 (DPI 150으로 고품질)
        matrix = fitz.Matrix(150/72, 150/72)  # 150 DPI
        pix = first_page.get_pixmap(matrix=matrix)
        
        # PIL Image로 변환
        img_data = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_data))
        
        # 이미지 최적화 (큰 이미지인 경우 리사이즈)
        image = optimize_image_size(image, max_dimension=1024)
        
        # base64로 변환
        buffered = io.BytesIO()
        image.save(buffered, format="PNG", optimize=True)
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        pdf_document.close()
        
        return f"data:image/png;base64,{img_base64}"
        
    except Exception as e:
        print(f"PDF processing error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"PDF 처리 중 오류가 발생했습니다: {str(e)}"
        )

async def process_image_to_base64(image_content: bytes) -> str:
    """
    이미지 파일을 처리하여 base64로 인코딩합니다.
    
    Args:
        image_content: 이미지 파일 바이트 내용
    
    Returns:
        str: base64 인코딩된 이미지 데이터 (data URL 형식)
    """
    try:
        # PIL Image로 열기
        image = Image.open(io.BytesIO(image_content))
        
        # 이미지 형식 확인 및 변환
        if image.format not in ["JPEG", "PNG", "GIF", "WEBP"]:
            # 지원되지 않는 형식은 PNG로 변환
            if image.mode in ['RGBA', 'LA']:
                image = image.convert("RGBA")
            else:
                image = image.convert("RGB")
            format_type = "PNG"
        else:
            format_type = image.format
        
        # 이미지 최적화
        image = optimize_image_size(image, max_dimension=1024)
        
        # base64로 변환
        buffered = io.BytesIO()
        image.save(buffered, format=format_type, optimize=True, quality=85)
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        mime_type = f"image/{format_type.lower()}"
        return f"data:{mime_type};base64,{img_base64}"
        
    except Exception as e:
        print(f"Image processing error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"이미지 처리 중 오류가 발생했습니다: {str(e)}"
        )

def optimize_image_size(image: Image.Image, max_dimension: int = 1024) -> Image.Image:
    """
    이미지 크기를 최적화합니다.
    
    Args:
        image: PIL Image 객체
        max_dimension: 최대 차원 크기 (픽셀)
    
    Returns:
        Image.Image: 최적화된 이미지
    """
    width, height = image.size
    
    # 이미지가 이미 작으면 그대로 반환
    if max(width, height) <= max_dimension:
        return image
    
    # 비율을 유지하면서 리사이즈
    if width > height:
        new_width = max_dimension
        new_height = int((height * max_dimension) / width)
    else:
        new_height = max_dimension
        new_width = int((width * max_dimension) / height)
    
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

def create_ai_analysis_request(
    base64_data: str,
    prompt: str,
    model: str,
    max_tokens: int,
    file_type: str
) -> dict:
    """
    AI 분석을 위한 요청 데이터를 생성합니다.
    
    Args:
        base64_data: base64 인코딩된 이미지 데이터
        prompt: 분석 프롬프트
        model: AI 모델명
        max_tokens: 최대 토큰 수
        file_type: 파일 타입 ("image" 또는 "pdf")
    
    Returns:
        dict: AI API 요청을 위한 데이터
    """
    # 파일 타입에 따른 프롬프트 보강
    if file_type == "pdf":
        enhanced_prompt = f"이것은 PDF 문서의 첫 번째 페이지입니다. {prompt}"
    else:
        enhanced_prompt = prompt
    
    return {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": enhanced_prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": base64_data
                        }
                    }
                ]
            }
        ],
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.7
    }

async def analyze_file_standard(request_data: dict) -> FileAnalysisResponse:
    """
    표준 방식으로 파일 분석을 수행합니다.
    
    Args:
        request_data: AI API 요청 데이터
    
    Returns:
        FileAnalysisResponse: 분석 결과
    """
    try:
        # OpenAI API 호출
        response = client.chat.completions.create(**request_data)
        
        content = response.choices[0].message.content
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }
        
        return FileAnalysisResponse(
            response=content,
            model=request_data["model"],
            usage=usage,
            file_type=request_data.get("file_type", "unknown")
        )
        
    except Exception as e:
        error_message = f"AI 분석 중 오류가 발생했습니다: {str(e)}"
        print(f"AI analysis error: {str(e)}")
        return FileAnalysisResponse(
            response=error_message,
            model=request_data["model"],
            usage={"error": str(e)},
            file_type=request_data.get("file_type", "unknown")
        )

async def analyze_file_streaming(request_data: dict):
    """
    스트리밍 방식으로 파일 분석을 수행합니다.
    
    Args:
        request_data: AI API 요청 데이터
    
    Returns:
        StreamingResponse: 스트리밍 응답
    """
    from fastapi.responses import StreamingResponse
    import json
    import asyncio
    
    model = request_data["model"]
    
    async def stream_generator():
        try:
            # 스트리밍 API 호출
            stream = client.chat.completions.create(
                **request_data,
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
            error_message = f"스트리밍 분석 중 오류가 발생했습니다: {str(e)}"
            print(f"Streaming analysis error: {str(e)}")
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

async def generate_chat_response(request: ChatRequest) -> ChatResponse:
    """
    대화 응답을 생성합니다.
    
    Args:
        request: ChatRequest 모델의 요청 데이터
    
    Returns:
        ChatResponse: 응답 데이터
    """
    try:
        # 모델 설정
        model = request.model or "gpt-4.1"
        
        # 모델 ID 매핑 (필요한 경우)
        model_mapping = {
            "gpt-4.1": "gpt-4.1",
            "gpt-4o": "gpt-4.1",
            "o4-mini": "gpt-4.1",
            "o3": "gpt-3.5-turbo"
        }
        
        # 모델 ID 변환
        api_model = model_mapping.get(model, model)
        
        # 입력 메시지 형식 변환 및 필터링
        input_messages = []
        for msg in request.messages:
            # 이전 웹 검색 관련 메시지 필터링 (삼일회계법인 등 특정 키워드 포함된 메시지 제외)
            if msg.role == "system" and any(keyword in msg.content for keyword in ["삼일회계법인", "웹 검색:", "검색 결과:"]):
                print(f"Filtering out system message containing search keywords: {msg.content[:30]}...")
                continue
            
            input_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # API 호출 준비
        api_params = {
            "model": api_model,
            "messages": input_messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens
        }
        
        # API 호출
        response = client.chat.completions.create(**api_params)
        
        # 응답 파싱
        content = response.choices[0].message.content
        
        # 사용량 정보
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }
        
        return ChatResponse(
            response=content,
            model=model,
            usage=usage,
            citations=[]
        )
        
    except Exception as e:
        # 에러 처리
        error_message = f"Error generating chat response: {str(e)}"
        print(f"Chat error: {str(e)}")
        return ChatResponse(
            response=error_message,
            model=model,
            usage={"error": str(e)}
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

async def generate_streaming_response(request: ChatRequest):
    """
    대화 응답을 생성하고 스트리밍 형식으로 반환합니다.
    
    Args:
        request: ChatRequest 모델의 요청 데이터
    
    Returns:
        스트리밍 응답 제너레이터
    """
    # 모델 설정
    model = request.model or "gpt-4.1"
    
    # 모델 ID 매핑 (필요한 경우)
    model_mapping = {
        "gpt-4.1": "gpt-4.1",
        "gpt-4o": "gpt-4.1",
        "o4-mini": "gpt-4.1",
        "o3": "gpt-3.5-turbo"
    }
    
    # 모델 ID 변환
    api_model = model_mapping.get(model, model)
    
    async def stream_generator():
        try:
            # 입력 메시지 형식 변환 및 필터링
            filtered_messages = []
            
            # 특수 필터링 단어 리스트
            filter_keywords = [
                "삼일회계법인", "주소는", "웹 검색:", "검색 결과:", 
                "bizbank.co.kr", "oldee.kr", "ytn.co.kr", "sedaily.com"
            ]
            
            for msg in request.messages:
                # 시스템 메시지 필터링
                if msg.role == "system" and any(keyword in msg.content for keyword in filter_keywords):
                    print(f"Filtering out system message with keywords: {msg.content[:50]}...")
                    continue
                
                # 사용자 메시지 중 웹 검색 접두사 제거
                if msg.role == "user" and msg.content.startswith("웹 검색:"):
                    msg.content = msg.content.replace("웹 검색:", "").strip()
                
                filtered_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # API 호출 준비
            api_params = {
                "model": api_model,
                "messages": filtered_messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "stream": True
            }
            
            # API 호출
            stream = client.chat.completions.create(**api_params)
            
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
            error_message = f"Error streaming response: {str(e)}"
            print(f"Streaming error: {str(e)}")
            yield f"data: {json.dumps({'content': error_message, 'is_streaming': False, 'error': str(e), 'model': model})}\n\n"
            yield f"data: [DONE]\n\n"
    
    # 비동기 이터레이터 반환
    return stream_generator()

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
        model = "gpt-4o-search-preview"  # 웹 검색 지원 모델로 고정
        
        # API 호출 준비
        messages = [
            {
                "role": "user",
                "content": request.query
            }
        ]
        
        # 웹 검색 옵션 설정
        web_search_options = {
            "search_context_size": request.search_context_size or "medium"
        }
        
        # API 호출 - temperature 제외
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=request.max_tokens,
            web_search_options=web_search_options
        )
        
        # 응답 파싱
        content = response.choices[0].message.content
        
        # 인용 정보 추출
        citations = []
        if hasattr(response.choices[0].message, 'annotations'):
            for annotation in response.choices[0].message.annotations:
                if annotation.type == 'url_citation':
                    citations.append({
                        'url': annotation.url_citation.url,
                        'title': annotation.url_citation.title,
                        'start_index': annotation.url_citation.start_index,
                        'end_index': annotation.url_citation.end_index
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