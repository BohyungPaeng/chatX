from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File, Form
from .models import ChatRequest, ChatResponse, ChatMessage, ImageAnalysisRequest, ImageAnalysisResponse, WebSearchRequest, WebSearchResponse
from .services import generate_chat_response, generate_streaming_response, analyze_image, analyze_image_streaming, perform_web_search, detect_file_type, convert_pdf_page_to_base64
from fastapi.responses import StreamingResponse
from typing import List, Optional
import base64
import os
from datetime import datetime
import io
from PIL import Image
import json

router = APIRouter()

from .pdf_processor import PDFBatchProcessor, PDF_BATCH_SIZE, PDF_PROCESSING_TIMEOUT, PDF_MAX_FILE_SIZE


@router.post("/process-pdf-batch")
async def process_pdf_in_batches(
    file: UploadFile = File(...),
    prompt: str = Form("PDF 문서를 분석해주세요."),
    model: str = Form("azure.gpt-4o-2024-11-20"),
    force_image_processing: bool = Form(False),
    stream: bool = Form(True)  # upload-image와 동일한 패턴
):
    """
    PDF 파일을 처리하여 응답 반환
    readable 여부에 따라 PyMuPDF 직접 추출 또는 이미지 변환 방식 선택
    stream 파라미터로 스트리밍/일반 응답 선택
    """
    try:
        print(f"=== PDF Processing Started ===")
        print(f"File: {file.filename}, Model: {model}, Force Image: {force_image_processing}, Stream: {stream}")
        
        # 파일 타입 검증
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="PDF 파일만 지원됩니다.")
        
        # 파일 크기 검증
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > PDF_MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400, 
                detail=f"파일 크기가 너무 큽니다. 최대 {PDF_MAX_FILE_SIZE // (1024*1024)}MB까지 지원합니다."
            )
        
        # 파일 내용 읽기
        pdf_content = await file.read()
        print(f"PDF content loaded: {len(pdf_content)} bytes")
        
        # 1단계: PDF 처리 방식 결정
        combined_text = ""
        processing_method = ""
        use_realtime_streaming = False  # 실시간 스트리밍 사용 여부
        
        if not force_image_processing:
            from .pdf_processor import enhanced_pdf_validation, extract_text_from_readable_pdf
            validation = enhanced_pdf_validation(pdf_content)
            
            if not validation['is_valid']:
                raise HTTPException(
                    status_code=400, 
                    detail=f"PDF 파일이 유효하지 않습니다: {validation.get('error', 'Unknown error')}"
                )
            
            is_readable = validation['is_readable']
            print(f"PDF validation: readable={is_readable}, score={validation.get('language_score', 'N/A')}")
            
            if is_readable:
                # readable: PyMuPDF 직접 텍스트 추출
                print("Using readable PDF processing")
                extracted_pages = extract_text_from_readable_pdf(pdf_content, file.filename)
                
                if not extracted_pages:
                    raise HTTPException(status_code=500, detail="텍스트 추출에 실패했습니다.")
                
                combined_text = "\n\n".join([
                    f"=== 페이지 {page['page_number']} ===\n{page['text_content']}"
                    for page in extracted_pages
                    if page.get('text_content', '').strip()
                ])
                processing_method = "direct_text_extraction"
        
        if not combined_text:  # readable하지 않은 경우 또는 강제 이미지 처리
            print("Using image PDF processing")
            from .pdf_processor import PDFBatchProcessor
            
            processor = PDFBatchProcessor(pdf_content, file.filename, model)
            
            if stream:
                # 스트리밍: 실시간 배치 처리 + 채팅 응답을 연결
                print("Using real-time streaming with chat response")
                use_realtime_streaming = True
                
                async def combined_pdf_streaming():
                    # 1단계: 실시간 배치 처리 스트리밍
                    batch_text = ""
                    async for chunk in processor.pdf_streaming_generator():
                        # 배치 처리 결과를 수집하면서 스트리밍
                        if chunk.startswith('data: '):
                            data_part = chunk[6:].split('\n\n')[0]
                            try:
                                data = json.loads(data_part)
                                if data.get('content'):
                                    batch_text += data['content']
                            except:
                                pass
                        yield chunk
                    
                    # 2단계: 배치 처리 완료 후 채팅 응답
                    if batch_text.strip():
                        yield f"data: {json.dumps({'content': '\\n\\n🤖 **AI 분석 결과:**\\n\\n', 'is_streaming': True, 'model': model})}\n\n"
                        
                        # ChatRequest 생성
                        system_message = f"""당신은 PDF 문서 분석 전문가입니다. 
다음 PDF 문서({file.filename})의 내용을 바탕으로 사용자의 질문에 정확하고 자세하게 답변해주세요.

문서 처리 방식: image_ocr_extraction
문서 내용:
{batch_text}

답변 시 문서에서 확인할 수 있는 내용을 구체적으로 인용하고, 페이지 번호를 참조해주세요."""
                        
                        chat_request = ChatRequest(
                            messages=[
                                ChatMessage(role="system", content=system_message),
                                ChatMessage(role="user", content=prompt)
                            ],
                            model=model,
                            temperature=0.7,
                            max_tokens=1000,
                            stream=True
                        )
                        
                        # 채팅 응답 스트리밍
                        stream_iterator = await generate_streaming_response(chat_request)
                        async for chat_chunk in stream_iterator:
                            yield chat_chunk
                    else:
                        yield f"data: {json.dumps({'content': '\\n\\n❌ 추출된 텍스트가 없어 AI 분석을 수행할 수 없습니다.', 'is_streaming': False, 'model': model})}\n\n"
                        yield f"data: [DONE]\\n\\n"
                
                return StreamingResponse(
                    combined_pdf_streaming(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "Content-Type": "text/event-stream"
                    }
                )
            else:
                # 일반 응답: 배치 처리 완료 후 결과 반환
                results, completed = processor.process_pdf_in_batches()
                
                if not results:
                    raise HTTPException(status_code=500, detail="PDF 페이지 처리에 실패했습니다.")
                
                combined_text = "\n\n".join([
                    f"=== 페이지 {page.get('page_number', 'N/A')} ===\n{page.get('text_content', '')}"
                    for page in results
                    if page.get('success') and page.get('text_content', '').strip()
                ])
                processing_method = "image_ocr_extraction"
        
        # 2단계: 일반 응답 (readable PDF 또는 non-readable PDF의 non-stream)
        if not use_realtime_streaming:
            if not combined_text.strip():
                raise HTTPException(status_code=500, detail="추출된 텍스트가 없습니다.")
            
            # 공통 시스템 메시지 생성 (중복 제거)
            system_message = f"""당신은 PDF 문서 분석 전문가입니다. 
다음 PDF 문서({file.filename})의 내용을 바탕으로 사용자의 질문에 정확하고 자세하게 답변해주세요.

문서 처리 방식: {processing_method}
문서 내용:
{combined_text}

답변 시 문서에서 직접 확인할 수 있는 내용을 구체적으로 인용하고, 페이지 번호를 참조해주세요."""
            
            chat_request = ChatRequest(
                messages=[
                    ChatMessage(role="system", content=system_message),
                    ChatMessage(role="user", content=prompt)
                ],
                model=model,
                temperature=0.7,
                max_tokens=1000,
                stream=stream
            )
            
            if stream:
                # 스트리밍 응답
                from .services import generate_streaming_response
                stream_iterator = await generate_streaming_response(chat_request)
                return StreamingResponse(
                    stream_iterator,
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "Content-Type": "text/event-stream"
                    }
                )
            else:
                # 일반 응답
                from .services import generate_chat_response
                response = await generate_chat_response(chat_request)
                return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Critical error in PDF processing: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF 처리 중 오류: {str(e)}")

@router.get("/pdf-processing-config")
def get_pdf_processing_config():
    """
    PDF 처리 설정 정보 반환
    
    Returns:
        Dict: 현재 PDF 처리 설정
    """
    return {
        "batch_size": PDF_BATCH_SIZE,
        "timeout_seconds": PDF_PROCESSING_TIMEOUT,
        "max_file_size_mb": PDF_MAX_FILE_SIZE // (1024 * 1024),
        "supported_formats": ["PDF"],
        "processing_method": "ThreadPoolExecutor with batch processing"
    }


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
        image_url = None
        
        # 방법 1: 파일 업로드
        if file:
            print(f"Debug - Processing uploaded file: {file.filename}")
            
            # 파일 타입 감지
            file_type = detect_file_type(file)
            if file_type not in ["image", "pdf"]:
                raise HTTPException(status_code=400, 
                    detail="지원되지 않는 파일 형식입니다. 이미지(JPEG, PNG, GIF, WEBP) 또는 PDF 파일만 지원합니다.")
            
            # 파일 내용 읽기
            contents = await file.read()
            
            # 파일 크기 확인 (25MB 제한)
            file_size = len(contents) / (1024 * 1024)  # MB 단위로 변환
            if file_size > 25:
                raise HTTPException(status_code=400, 
                                   detail="파일 크기가 너무 큽니다. 최대 25MB까지 지원합니다.")
            
            # PDF 파일인 경우 이미지로 변환
            if file_type == "pdf":
                print("Debug - Converting PDF to image")
                try:
                    image_url = convert_pdf_page_to_base64(contents)
                    prompt = f"이것은 PDF 문서의 첫 번째 페이지입니다. {prompt}"
                except Exception as e:
                    print(f"Debug - PDF conversion error: {str(e)}")
                    raise HTTPException(status_code=400, detail=f"PDF 처리 중 오류: {str(e)}")
            else:
                # 일반 이미지 처리 (기존 PIL 처리 로직 포함)
                print("Debug - Processing regular image file")
                try:
                    # PIL을 사용하여 이미지 포맷 확인 및 변환
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
                    
                    # 파일을 base64로 인코딩
                    base64_image_data = base64.b64encode(contents).decode("utf-8")
                    image_url = f"data:{content_type};base64,{base64_image_data}"
                    
                except Exception as e:
                    print(f"Debug - Critical error processing image: {str(e)}")
                    raise HTTPException(status_code=400, detail="이미지 파일을 처리할 수 없습니다. 지원되는 형식(JPEG, PNG, GIF, WEBP)인지 확인하세요.")
                
        # 방법 2: Base64 인코딩된 이미지 (기존 복잡한 로직 유지)
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
                if file_size > 25:
                    raise HTTPException(status_code=400, 
                                    detail="이미지 크기가 너무 큽니다. 최대 25MB까지 지원합니다.")
                
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
            model = "gpt-4.1"
        
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
        file.file.seek(0, 2)  # 파일 끝으로 이동
        file_size = file.file.tell()  # 현재 위치 = 파일 크기
        file.file.seek(0)  # 파일 시작으로 되돌리기
        
        max_size_bytes = 25 * 1024 * 1024  # 25MB
        if file_size > max_size_bytes:
            return {
                "valid": False,
                "error": "파일 크기가 너무 큽니다. 최대 25MB까지 지원합니다.",
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
def get_supported_file_types() -> dict:  # async 제거
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