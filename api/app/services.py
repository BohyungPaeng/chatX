import openai
from .config import OPENAI_API_KEY, GPT_MODEL
from .models import ChatMessage, ChatRequest, ChatResponse, ImageAnalysisRequest, ImageAnalysisResponse, WebSearchRequest, WebSearchResponse
from fastapi.responses import StreamingResponse
import json
import asyncio

# OpenAI 클라이언트 설정
client = openai.OpenAI(api_key=OPENAI_API_KEY)

import io
import base64
from PIL import Image
import fitz  # PyMuPDF for PDF processing
from fastapi import HTTPException, UploadFile
# services.py 파일에 추가할 함수들

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

def convert_pdf_page_to_base64(pdf_content: bytes) -> str:
    """
    PDF 바이트를 첫 페이지 이미지로 변환하여 base64 반환
    50MB까지 지원하도록 개선
    """
    try:
        # PDF 크기 체크 (50MB 제한)
        pdf_size_mb = len(pdf_content) / (1024 * 1024)
        if pdf_size_mb > 50:
            raise ValueError(f"PDF 파일이 너무 큽니다. 크기: {pdf_size_mb:.2f}MB (최대 50MB)")
            
        # PDF 문서 열기
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        
        if len(doc) == 0:
            raise ValueError("PDF 파일이 비어있습니다.")
            
        # 첫 번째 페이지를 가져옴
        page = doc[0]
        # 300 DPI 변환을 위한 매트릭스 생성 (기본 72 DPI 기준 스케일링)
        matrix = fitz.Matrix(300/72, 300/72)
        # 페이지를 300 DPI 이미지로 변환
        pix = page.get_pixmap(matrix=matrix)
        # 이미지 데이터를 바이트로 변환
        img_bytes = pix.tobytes("png")
        # base64로 인코딩
        base64_image = base64.b64encode(img_bytes).decode('utf-8')
        doc.close()
        
        print(f"PDF 변환 완료: {pdf_size_mb:.2f}MB -> 이미지 변환됨")
        return f"data:image/png;base64,{base64_image}"
        
    except Exception as e:
        print(f"Error converting PDF: {str(e)}")
        raise Exception(f"PDF 변환 실패: {str(e)}")

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
            # 일반 모드에서는 이미지 URL이 있는 메시지와 웹 검색 관련 메시지만 제외
            if msg.role == "system" and any(keyword in msg.content for keyword in ["삼일회계법인", "웹 검색:", "검색 결과:"]):
                print(f"Filtering out system message containing search keywords: {msg.content[:30]}...")
                continue
            
            input_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        if model.startswith("azure."):
            pwc = await _get_pwc_model(model)
            # PWC GPT 호출 (OpenAI와 유사하게)
            response = await pwc.run(
                messages=input_messages,
                max_tokens=request.max_tokens,
                model=model
            )
            # response는 dict로 가정 (OpenAI와 유사하게)
            content = response["choices"][0]["message"]["content"]
            usage = response.get("usage", {})
            return ChatResponse(
                response=content,
                model=model,
                usage=usage,
                citations=[]
            )
        else:
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
    
async def _get_pwc_model(model_name: str) -> 'AsyncPwCGPTModel':
    """PWC GPT 모델 인스턴스를 생성하고 헬스체크를 수행합니다."""
    from .pwc_gpt import AsyncPwCGPTModel
    
    pwc = AsyncPwCGPTModel(default_model_name=model_name)
    status = await pwc.health_check()
    if status != 200:
        print(f"PWC GPT health check failed: {status}")
    return pwc

async def analyze_image(request: ImageAnalysisRequest) -> ImageAnalysisResponse:
    """
    OpenAI API 또는 PWC GPT를 사용하여 이미지를 분석합니다.
    
    Args:
        request: ImageAnalysisRequest 모델의 요청 데이터
    
    Returns:
        ImageAnalysisResponse: 이미지 분석 결과
    """
    model = request.model or "gpt-4.1"

    
    try:
        if not request.image_url:
            raise ValueError("유효한 이미지 URL이 필요합니다.")
        
        content = None
        usage = {}
        
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
            # 기존 OpenAI 방식
            messages = []
            
            if request.conversation_history:
                for msg in request.conversation_history:
                    messages.append({"role": msg.role, "content": msg.content})
            
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": request.prompt},
                    {"type": "image_url", "image_url": {"url": request.image_url}}
                ]
            })
            
            response = client.chat.completions.create(
                model=model, messages=messages, max_tokens=request.max_tokens
            )
            
            content = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        
        # 공통 로깅 및 응답
        print(f"Request max_tokens: {request.max_tokens}")
        if "completion_tokens" in usage:
            print(f"Response tokens used: {usage['completion_tokens']}")
        elif "elapsed" in usage:
            print(f"PWC GPT elapsed time: {usage['elapsed']:.2f}s")
        print(content[:100])

        return ImageAnalysisResponse(response=content, model=model, usage=usage)
        
    except Exception as e:
        error_message = f"Error in analyze_image"
        print(f"analyze_image error: {type(e).__name__}: {str(e)}")
        return ImageAnalysisResponse(
            response=error_message, 
            model=model, 
            usage={"error": str(e), "error_type": type(e).__name__}
        )

async def analyze_image_streaming(request: ImageAnalysisRequest):
    """
    이미지를 분석하고 스트리밍 응답을 생성합니다.
    """
    model = request.model or "gpt-4.1"
    
    async def stream_generator():
        try:
            if not request.image_url:
                raise ValueError("유효한 이미지 URL이 필요합니다.")
            
            # 공통 메시지 구성
            messages = []
            if request.conversation_history:
                for msg in request.conversation_history:
                    messages.append({"role": msg.role, "content": msg.content})
            
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": request.prompt},
                    {"type": "image_url", "image_url": {"url": request.image_url}}
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
                # OpenAI 스트리밍
                print(f"Using OpenAI streaming for model: {model}")
                stream = client.chat.completions.create(
                    model=model, messages=messages, max_tokens=request.max_tokens, stream=True
                )
                
                # OpenAI 스트리밍 처리 (PWC GPT와 동일한 패턴)
                for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        content = chunk.choices[0].delta.content
                        collected_messages.append(content)
                        yield f"data: {json.dumps({'content': content, 'is_streaming': True, 'model': model})}\n\n"
                        await asyncio.sleep(0)
            
            # 공통 완료 처리
            completion_info = {
                'content': '', 'is_streaming': False, 'model': model,
                'usage': {'completion_tokens': len(collected_messages)}
            }
            yield f"data: {json.dumps(completion_info)}\n\n"
            yield f"data: [DONE]\n\n"
            
        except Exception as e:
            error_message = f"Error in analyze_image_streaming"
            print(f"analyze_image_streaming error: {str(e)}")
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
    model = model_mapping.get(model, model)
    async def stream_generator():
        try:
            # 입력 메시지 형식 변환 및 필터링
            filtered_messages = []
            # 향후 conversation_history가 추가될 경우 아래 주석을 참고하여 messages를 생성할 수 있습니다.
            # messages = []
            # if hasattr(request, 'conversation_history') and request.conversation_history:
            #     for msg in request.conversation_history:
            #         messages.append({"role": msg.role, "content": msg.content})
            # else:
            #     for msg in request.messages:
            #         messages.append({"role": msg.role, "content": msg.content})
            
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

            collected_messages = []
            if model.startswith("azure."):
                # PWC GPT 스트리밍
                pwc = await _get_pwc_model(model)
                async for chunk in pwc.run_stream(
                    messages=filtered_messages,
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
                # API 호출 준비
                api_params = {
                    "model": model,
                    "messages": filtered_messages,
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "stream": True
                }
                # API 호출
                stream = client.chat.completions.create(**api_params)
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
    
async def chunk_pdf_document(filename: str, debug_mode: bool = True):
    """
    PDF 문서 청킹 - 전체 문서 통합 방식
    
    Args:
        filename: PDF 파일명
        debug_mode: 디버깅 모드 (3가지 방식 비교)
    
    Returns:
        List[Chunk]: 청킹 결과 (cosine)
    """
    try:
        from .cache_manager import pdf_cache_manager
        from .doc_chunker import DocumentChunker
        
        # 캐시 로드
        cache_data = pdf_cache_manager.load(filename)
        if not cache_data:
            raise ValueError(f"PDF 캐시를 찾을 수 없습니다: {filename}")
        
        print(f"🔍 DEBUG: 원본 {len(cache_data.get('page_texts', []))} 페이지 감지")
        
        # chunker 생성
        chunker = DocumentChunker(chunking_method='cosine')
        chunks = chunker.chunk_document(cache_data, filename)
        
        if debug_mode:
            # 3가지 방식 비교 (analyze만 사용)
            methods = ['cosine', 'jaccard', 'simple']
            chunk_counts = []
            
            for method in methods:
                chunker.chunking_method = method
                if method == 'cosine':
                    test_chunks = chunks  # 이미 만든 것 재사용
                else:
                    test_chunks = chunker.chunk_document(cache_data, filename)
                
                chunker._analyze_chunks(test_chunks, method)
                chunk_counts.append(len(test_chunks))
            
            print(f"\n📊 === 3가지 방식 비교 ===")
            print(f"COSINE: {chunk_counts[0]}개 (선택됨)")
            print(f"JACCARD: {chunk_counts[1]}개")
            print(f"SIMPLE: {chunk_counts[2]}개")
        
        print(f"🔍 DEBUG: 총 {len(chunks)}개 청크 생성")
        print(f"Successfully chunked {filename}: {len(chunks)} chunks created (cosine)")
        return chunks
        
    except Exception as e:
        print(f"Error chunking PDF document {filename}: {str(e)}")
        raise Exception(f"PDF 청킹 중 오류: {str(e)}")