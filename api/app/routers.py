from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File, Form
from .models import ChatRequest, ChatResponse, ChatMessage, ImageAnalysisRequest, ImageAnalysisResponse, WebSearchRequest, WebSearchResponse
from .services import generate_chat_response, generate_streaming_response, analyze_image, analyze_image_streaming, perform_web_search
from fastapi.responses import StreamingResponse
from typing import List, Optional
import base64
import os
from datetime import datetime
import io
from PIL import Image
import json

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    채팅 메시지를 처리하고 GPT 응답을 반환합니다.
    
    Args:
        request: 채팅 요청 데이터
    
    Returns:
        ChatResponse: 생성된 응답
    """
    # 스트리밍 요청이면 스트리밍 응답을 반환
    if request.stream:
        # 비동기 이터레이터 생성
        stream_iterator = await generate_streaming_response(request)
        return StreamingResponse(
            stream_iterator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
        
    # 일반 요청 처리
    try:
        response = await generate_chat_response(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream_post(request: ChatRequest):
    """
    채팅 메시지를 처리하고 스트리밍 응답을 반환합니다. (POST 메서드)
    
    Args:
        request: 채팅 요청 데이터
    
    Returns:
        StreamingResponse: 스트리밍 응답
    """
    # 비동기 이터레이터 생성
    stream_iterator = await generate_streaming_response(request)
    return StreamingResponse(
        stream_iterator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


@router.get("/chat/stream")
async def chat_stream_get(
    message: str = Query(..., description="사용자 메시지"),
    model: Optional[str] = Query(None, description="사용할 모델"),
    temperature: float = Query(0.7, description="온도 설정"),
    max_tokens: int = Query(1000, description="최대 토큰 수")
):
    """
    채팅 메시지를 처리하고 스트리밍 응답을 반환합니다. (GET 메서드, EventSource 호환)
    
    Args:
        message: 사용자 메시지
        model: 사용할 모델 ID
        temperature: 온도 설정
        max_tokens: 최대 토큰 수
    
    Returns:
        StreamingResponse: 스트리밍 응답
    """
    # 간단한 단일 메시지용 요청 생성
    request = ChatRequest(
        messages=[ChatMessage(role="user", content=message)],
        model=model,
        temperature=temperature,
        max_tokens=max_tokens
    )
    
    # 비동기 이터레이터 생성
    stream_iterator = await generate_streaming_response(request)
    return StreamingResponse(
        stream_iterator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


@router.post("/analyze-image", response_model=ImageAnalysisResponse)
async def analyze_image_from_url(request: ImageAnalysisRequest):
    """
    URL로부터 이미지를 분석하고 설명을 반환합니다.
    
    Args:
        request: 이미지 분석 요청 데이터
    
    Returns:
        ImageAnalysisResponse: 이미지 분석 결과 또는 StreamingResponse
    """
    try:
        # 스트리밍 요청인 경우 스트리밍 응답을 반환
        if request.stream:
            # 비동기 스트리밍 함수 직접 호출
            return await analyze_image_streaming(request)
        
        # 일반 요청인 경우 표준 응답을 반환
        response = await analyze_image(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-image")
async def analyze_uploaded_image(
    file: Optional[UploadFile] = None,
    base64_image: Optional[str] = Form(None),
    prompt: str = Form("이 이미지에 대해 자세히 설명해주세요."),
    model: Optional[str] = Form(None),
    max_tokens: int = Form(1000),
    detail: str = Form("auto"),
    stream: bool = Form(False),
    conversation_history: Optional[str] = Form(None)
):
    """
    업로드된 이미지를 분석하고 설명을 반환합니다.
    
    Args:
        file: 업로드된 이미지 파일 (선택적)
        base64_image: Base64 인코딩된(data:image/xxx;base64,으로 시작하는) 이미지 URL (선택적)
        prompt: 분석에 사용할 프롬프트
        model: 사용할 모델 ID
        max_tokens: 최대 토큰 수
        detail: 이미지 상세도 (low/high/auto)
        stream: 스트리밍 응답 반환 여부
        conversation_history: 이전 대화 기록 (JSON 문자열, 선택적)
    
    Returns:
        ImageAnalysisResponse 또는 StreamingResponse: 이미지 분석 결과
    """
    try:
        contents = None
        content_type = None
        image_url = None
        
        print(f"Debug - Request received with file: {file is not None}, base64_image: {base64_image is not None}")
        
        # 방법 1: 파일 업로드
        if file:
            print(f"Debug - Processing uploaded file: {file.filename}")
            # 지원되는 이미지 형식 확인 - 확장자로 판단
            file_ext = file.filename.split('.')[-1].lower()
            print(f"Debug - File extension: {file_ext}")
            
            # 파일 내용 읽기
            contents = await file.read()
            
            # PIL을 사용하여 이미지 포맷 확인 및 변환
            try:
                img = None
                with io.BytesIO(contents) as img_buffer:
                    try:
                        img = Image.open(img_buffer)
                        img.load()  # 이미지를 완전히 로드하여 검증
                        print(f"Debug - Detected image format: {img.format}")
                        
                        # AVIF 또는 지원되지 않는 형식이거나 형식을 감지할 수 없는 경우 PNG로 변환
                        if not img.format or img.format not in ["JPEG", "PNG", "GIF", "WEBP"]:
                            print(f"Debug - Converting {img.format or 'unknown format'} to PNG")
                            output = io.BytesIO()
                            
                            # RGB 모드로 변환 (알파 채널이 있는 경우 RGBA)
                            if img.mode in ['RGBA', 'LA']:
                                img_converted = img.convert("RGBA")
                            else:
                                img_converted = img.convert("RGB")
                            
                            # PNG로 저장
                            img_converted.save(output, format="PNG")
                            contents = output.getvalue()
                            content_type = "image/png"
                        else:
                            # 감지된 형식 사용
                            content_type = f"image/{img.format.lower()}"
                    except Exception as e:
                        print(f"Debug - Error processing image with first attempt: {str(e)}")
                        # 첫 번째 시도가 실패하면 다른 방법으로 재시도
                        img_buffer.seek(0)  # 버퍼 위치 초기화
                        try:
                            # RGB 모드로 직접 변환 시도
                            output = io.BytesIO()
                            img = Image.new('RGB', (800, 600), (255, 255, 255))
                            img.save(output, format="PNG")
                            contents = output.getvalue()
                            content_type = "image/png"
                            print(f"Debug - Created fallback blank PNG image")
                        except Exception as e2:
                            print(f"Debug - Failed to create fallback image: {str(e2)}")
                            raise HTTPException(status_code=400, 
                                              detail="이미지 처리에 실패했습니다. 다른 이미지를 사용해주세요.")
            except Exception as e:
                print(f"Debug - Critical error processing image: {str(e)}")
                raise HTTPException(status_code=400, detail="이미지 파일을 처리할 수 없습니다. 지원되는 형식(JPEG, PNG, GIF, WEBP)인지 확인하세요.")
            
            # 파일 크기 확인 (20MB 제한)
            file_size = len(contents) / (1024 * 1024)  # MB 단위로 변환
            if file_size > 20:
                raise HTTPException(status_code=400, 
                                   detail="이미지 크기가 너무 큽니다. 최대 20MB까지 지원합니다.")
            
            # 파일을 base64로 인코딩 - OpenAI 예제와 동일한 형식
            base64_image_data = base64.b64encode(contents).decode("utf-8")
            image_url = f"data:{content_type};base64,{base64_image_data}"
            
            print(f"Debug - Created base64 image URL, size: {file_size:.2f}MB, format: {content_type}")
                
        # 방법 2: Base64 인코딩된 이미지
        elif base64_image:
            print(f"Debug - Processing base64 image")
            # data:image/ 형식 확인
            if not base64_image.startswith('data:image/'):
                raise HTTPException(status_code=400, 
                                  detail="잘못된 base64 이미지 형식입니다. 'data:image/xxx;base64,' 형식이어야 합니다.")
            
            # 컨텐츠 타입과 base64 데이터 분리
            try:
                content_type_part = base64_image.split(';')[0]
                content_type = content_type_part.split(':')[1]
                
                # Base64 데이터 추출
                base64_parts = base64_image.split(',')
                if len(base64_parts) < 2:
                    raise HTTPException(status_code=400, detail="잘못된 Base64 이미지 형식입니다.")
                
                base64_data = base64_parts[1]
                
                # Base64 디코딩하여 유효성 검사
                try:
                    contents = base64.b64decode(base64_data)
                except Exception as e:
                    print(f"Debug - Base64 decoding error: {str(e)}")
                    raise HTTPException(status_code=400, detail="올바른 Base64 형식이 아닙니다.")
                
                # PIL을 사용하여 이미지 포맷 확인 및 변환
                try:
                    img = None
                    with io.BytesIO(contents) as img_buffer:
                        try:
                            img = Image.open(img_buffer)
                            img.load()  # 이미지를 완전히 로드하여 검증
                            print(f"Debug - Detected image format from base64: {img.format}")
                            
                            # AVIF 또는 지원되지 않는 형식이거나 형식을 감지할 수 없는 경우 PNG로 변환
                            if not img.format or img.format not in ["JPEG", "PNG", "GIF", "WEBP"]:
                                print(f"Debug - Converting {img.format or 'unknown format'} to PNG")
                                output = io.BytesIO()
                                
                                # RGB 모드로 변환 (알파 채널이 있는 경우 RGBA)
                                if img.mode in ['RGBA', 'LA']:
                                    img_converted = img.convert("RGBA")
                                else:
                                    img_converted = img.convert("RGB")
                                
                                # PNG로 저장
                                img_converted.save(output, format="PNG")
                                contents = output.getvalue()
                                content_type = "image/png"
                                
                                # 새로운 base64 이미지 생성
                                base64_image_data = base64.b64encode(contents).decode("utf-8")
                                image_url = f"data:{content_type};base64,{base64_image_data}"
                            else:
                                # 원본 이미지 URL 사용하기 전에 형식 확인 
                                detected_format = img.format.lower()
                                if detected_format in ["jpeg", "png", "gif", "webp"]:
                                    content_type = f"image/{detected_format}" 
                                    # 형식이 올바르더라도, 일관성을 위해 재인코딩
                                    output = io.BytesIO()
                                    img.save(output, format=img.format)
                                    contents = output.getvalue()
                                    base64_image_data = base64.b64encode(contents).decode("utf-8")
                                    image_url = f"data:{content_type};base64,{base64_image_data}"
                                else:
                                    # 감지된 형식이 지원되지 않는 경우
                                    print(f"Debug - Detected unsupported format: {detected_format}")
                                    output = io.BytesIO()
                                    if img.mode in ['RGBA', 'LA']:
                                        img_converted = img.convert("RGBA")
                                    else:
                                        img_converted = img.convert("RGB")
                                    img_converted.save(output, format="PNG")
                                    contents = output.getvalue()
                                    content_type = "image/png"
                                    base64_image_data = base64.b64encode(contents).decode("utf-8")
                                    image_url = f"data:{content_type};base64,{base64_image_data}"
                        except Exception as e:
                            print(f"Debug - Error processing base64 image with first attempt: {str(e)}")
                            # 첫 번째 시도가 실패하면 다른 방법으로 재시도
                            img_buffer.seek(0)  # 버퍼 위치 초기화
                            try:
                                # RGB 모드로 직접 변환 시도
                                output = io.BytesIO()
                                img = Image.new('RGB', (800, 600), (255, 255, 255))
                                img.save(output, format="PNG")
                                contents = output.getvalue()
                                content_type = "image/png"
                                base64_image_data = base64.b64encode(contents).decode("utf-8")
                                image_url = f"data:{content_type};base64,{base64_image_data}"
                                print(f"Debug - Created fallback blank PNG image")
                            except Exception as e2:
                                print(f"Debug - Failed to create fallback image: {str(e2)}")
                                raise HTTPException(status_code=400, 
                                                  detail="이미지 처리에 실패했습니다. 다른 이미지를 사용해주세요.")
                except Exception as e:
                    print(f"Debug - Critical error processing base64 image: {str(e)}")
                    raise HTTPException(status_code=400, detail="이미지를 처리할 수 없습니다. 지원되는 형식(JPEG, PNG, GIF, WEBP)인지 확인하세요.")
                
                # 크기 확인
                file_size = len(contents) / (1024 * 1024)  # MB 단위로 변환
                if file_size > 20:
                    raise HTTPException(status_code=400, 
                                    detail="이미지 크기가 너무 큽니다. 최대 20MB까지 지원합니다.")
                
                print(f"Debug - Processed base64 image, size: {file_size:.2f}MB, format: {content_type}")
            except HTTPException:
                raise
            except Exception as e:
                print(f"Debug - Error processing base64 image: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Base64 이미지 처리 오류: {str(e)}")
        else:
            raise HTTPException(status_code=400, 
                               detail="파일 또는 base64 이미지가 필요합니다. 이미지를 제공해주세요.")
            
        if not image_url:
            raise HTTPException(status_code=500, detail="이미지 URL을 생성하지 못했습니다.")
            
        print(f"Debug - Final image_url starts with: {image_url[:30]}...")
        
        # 상세도 옵션 유효성 검사
        if detail not in ["low", "high", "auto"]:
            detail = "auto"  # 기본값으로 설정
        
        # 기본 모델 설정
        if not model:
            model = "gpt-4.1"  # gpt-4-vision-preview 대신 gpt-4.1 사용
        
        print(f"Debug - Creating ImageAnalysisRequest with model: {model}")
        
        # 대화 컨텍스트 파싱
        chat_history = None
        if conversation_history:
            try:
                chat_history = json.loads(conversation_history)
                print(f"Debug - Conversation history loaded with {len(chat_history)} messages")
            except Exception as e:
                print(f"Debug - Error parsing conversation history: {str(e)}")
                # 오류가 발생해도 계속 진행 (채팅 기록 없이)
        
        # 이미지 분석 요청 생성
        request = ImageAnalysisRequest(
            image_url=image_url,
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            detail=detail,
            stream=stream,
            conversation_history=chat_history
        )
        
        # 이미지 분석 (스트리밍 또는 일반 요청)
        if stream:
            # 스트리밍 응답 처리
            return await analyze_image_streaming(request)
        else:
            # 일반 응답 처리
            response = await analyze_image(request)
            return response
        
    except HTTPException as e:
        # HTTP 예외는 그대로 전달
        raise e
    except Exception as e:
        print(f"Error in analyze_uploaded_image: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from .models import FileAnalysisResponse, ProcessedFileInfo, FileUploadMetadata
from .services import process_uploaded_file, detect_file_type, validate_file_size
import time
from typing import Optional

@router.post("/upload-file", response_model=FileAnalysisResponse)
async def analyze_uploaded_file(
    file: UploadFile = File(...),
    prompt: str = Form("이 파일에 대해 자세히 설명해주세요."),
    model: str = Form("gpt-4.1"),
    max_tokens: int = Form(1000),
    stream: bool = Form(False)
):
    """
    파일(이미지/PDF)을 업로드하고 AI 분석을 수행합니다.
    
    Args:
        file: 업로드된 파일 (이미지 또는 PDF)
        prompt: 분석을 위한 프롬프트
        model: 사용할 AI 모델
        max_tokens: 최대 토큰 수
        stream: 스트리밍 응답 여부
    
    Returns:
        FileAnalysisResponse: 파일 분석 결과
    """
    start_time = time.time()
    
    try:
        print(f"Processing file: {file.filename}, content-type: {file.content_type}")
        
        # 파일 타입 감지
        file_type = detect_file_type(file)
        if file_type == "unknown":
            raise HTTPException(
                status_code=400,
                detail="지원되지 않는 파일 형식입니다. 이미지(JPEG, PNG, GIF, WEBP) 또는 PDF 파일만 지원합니다."
            )
        
        # 파일 크기 검증
        await validate_file_size(file, max_size_mb=25)
        
        # 파일 분석 수행
        result = await process_uploaded_file(
            file=file,
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            stream=stream
        )
        
        processing_time = int((time.time() - start_time) * 1000)
        print(f"File processing completed in {processing_time}ms")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in analyze_uploaded_file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/file-info")
async def get_file_info(file: UploadFile = File(...)) -> FileUploadMetadata:
    """
    업로드된 파일의 메타데이터를 반환합니다.
    
    Args:
        file: 업로드된 파일
    
    Returns:
        FileUploadMetadata: 파일 메타데이터
    """
    try:
        # 파일 크기 계산
        file.file.seek(0, 2)  # 파일 끝으로 이동
        file_size = file.file.tell()  # 현재 위치 = 파일 크기
        file.file.seek(0)  # 파일 시작으로 되돌리기
        
        # 파일 타입 감지
        file_type = detect_file_type(file)
        
        return FileUploadMetadata(
            filename=file.filename or "unknown",
            content_type=file.content_type or "unknown",
            file_size=file_size,
            file_type=file_type
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"파일 정보 처리 중 오류가 발생했습니다: {str(e)}"
        )

@router.post("/validate-file")
async def validate_file(file: UploadFile = File(...)) -> dict:
    """
    파일 유효성을 검증합니다.
    
    Args:
        file: 업로드된 파일
    
    Returns:
        dict: 검증 결과
    """
    try:
        # 파일 타입 검증
        file_type = detect_file_type(file)
        if file_type == "unknown":
            return {
                "valid": False,
                "error": "지원되지 않는 파일 형식입니다.",
                "supported_types": ["이미지 (JPEG, PNG, GIF, WEBP)", "PDF"]
            }
        
        # 파일 크기 검증
        try:
            await validate_file_size(file, max_size_mb=25)
        except HTTPException as e:
            return {
                "valid": False,
                "error": e.detail,
                "max_size": "25MB"
            }
        
        return {
            "valid": True,
            "file_type": file_type,
            "message": "파일이 유효합니다."
        }
        
    except Exception as e:
        return {
            "valid": False,
            "error": f"파일 검증 중 오류가 발생했습니다: {str(e)}"
        }

@router.get("/supported-file-types")
async def get_supported_file_types() -> dict:
    """
    지원되는 파일 타입 목록을 반환합니다.
    
    Returns:
        dict: 지원되는 파일 타입 정보
    """
    return {
        "supported_types": {
            "images": {
                "mime_types": ["image/jpeg", "image/png", "image/gif", "image/webp"],
                "extensions": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
                "description": "이미지 파일"
            },
            "documents": {
                "mime_types": ["application/pdf"],
                "extensions": [".pdf"],
                "description": "PDF 문서"
            }
        },
        "limits": {
            "max_file_size": "25MB",
            "max_files_per_request": 1
        },
        "features": {
            "pdf_preview": "PDF 첫 페이지 이미지 변환",
            "image_optimization": "자동 이미지 크기 최적화",
            "streaming_analysis": "실시간 분석 결과 스트리밍"
        }
    }

@router.get("/models")
async def get_available_models():
    """
    사용 가능한 모델 목록을 반환합니다.
    """
    # 요청된 모델 목록 반환
    models = [
        {"id": "gpt-4.1", "name": "GPT-4.1"},
        {"id": "gpt-4o", "name": "GPT-4o"},
        {"id": "o4-mini", "name": "O4-mini"},
        {"id": "o3", "name": "O3"}
    ]
    return {"models": models}


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