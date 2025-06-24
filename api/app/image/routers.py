from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
import base64
import io
from PIL import Image
import json

from .models import ImageAnalysisRequest, ImageAnalysisResponse, ImageGenResponse
from .services import analyze_image, analyze_image_streaming


from .services import analyze_image, analyze_image_streaming, generate_image
from fastapi.responses import StreamingResponse

router = APIRouter()


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
    


@router.post("/image-generation", response_model=ImageGenResponse)
async def image_generation(
    filename: str = Form(...),
    type: str = Form("icon"),
):
    """
    - filename: 업로드된 파일명 (e.g. "mypic.png")
    - type: "icon" (현재는 아이콘만 지원)
    """
    # 1) title은 확장자 제거
    title = filename.rsplit(".", 1)[0]

    if type != "icon":
        raise HTTPException(400, detail=f"unsupported type: {type}")

    # 2) 원본 Base64 얻기 (1024×1024)
    try:
        raw_b64 = await generate_image(title)
    except Exception as e:
        print(f"🔥 Icon generation error: {e}")  # 서버 로그용
        raise HTTPException(400, detail=f"Icon generation failed: {str(e)}")

    # 3) 디코딩 → PIL → 256×256 리사이즈
    img = Image.open(io.BytesIO(base64.b64decode(raw_b64)))
    img256 = img.resize((256, 256), Image.LANCZOS)

    # 4) 메모리 상에 PNG 최적화 저장 → Base64 재인코딩
    buf = io.BytesIO()
    img256.save(buf, format="PNG", optimize=True)
    resized_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return ImageGenResponse(b64=resized_b64)