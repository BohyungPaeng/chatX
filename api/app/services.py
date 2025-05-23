import openai
from .config import OPENAI_API_KEY, GPT_MODEL
from .models import ChatMessage, ChatRequest, ChatResponse, ImageAnalysisRequest, ImageAnalysisResponse, WebSearchRequest, WebSearchResponse, FileUploadResponse, FileQueryRequest, FileQueryResponse, FileAnnotation
from fastapi.responses import StreamingResponse
import json
import asyncio
import os
from io import BytesIO
from pathlib import Path
from fastapi import UploadFile
import httpx
import ssl
from openai import APIConnectionError
from typing import List, Dict

# SSL 인증서 검증 비활성화
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# httpx 클라이언트 설정
http_client = httpx.Client(verify=False)

# OpenAI 클라이언트 설정
client = openai.OpenAI(
    api_key=OPENAI_API_KEY,
    http_client=httpx.Client(verify=False),
    max_retries=3,
    timeout=60.0
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

# 다중 파일 업로드 함수
async def upload_multiple_files_to_openai(files_data: List[tuple]) -> Dict:
    """
    여러 파일을 OpenAI에 업로드하고 하나의 벡터 스토어에 추가합니다.
    
    Args:
        files_data: [(file_content, filename), ...] 형태의 리스트
    
    Returns:
        Dict: 업로드 결과
    """
    try:
        # 벡터 스토어 생성
        vector_store = client.vector_stores.create(
            name=f"ChatX Multi-File Vector Store"
        )
        
        uploaded_files = []
        file_ids = []
        
        # 각 파일을 업로드
        for file_content, filename in files_data:
            # 임시 디렉토리 생성
            temp_dir = Path("temp")
            temp_dir.mkdir(exist_ok=True)
            
            # 임시 파일 저장
            temp_file_path = temp_dir / filename
            with open(temp_file_path, "wb") as buffer:
                buffer.write(file_content)
            
            # OpenAI에 파일 업로드
            with open(temp_file_path, "rb") as file:
                uploaded_file = client.files.create(
                    file=file,
                    purpose="assistants"
                )
            
            # 임시 파일 삭제
            if temp_file_path.exists():
                os.remove(temp_file_path)
            
            uploaded_files.append({
                "file_id": uploaded_file.id,
                "filename": filename
            })
            file_ids.append(uploaded_file.id)
            
            print(f"파일 업로드 성공: {filename} -> {uploaded_file.id}")
        
        # 벡터 스토어에 모든 파일 추가
        if file_ids:
            file_batch = client.vector_stores.file_batches.create(
                vector_store_id=vector_store.id,
                file_ids=file_ids
            )
            print(f"벡터 스토어에 {len(file_ids)}개 파일 추가 완료: {vector_store.id}")
        
        return {
            "success": True,
            "vector_store_id": vector_store.id,
            "uploaded_files": uploaded_files
        }
        
    except Exception as e:
        print(f"다중 파일 업로드 오류: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# 기존 단일 파일 업로드 함수 (호환성 유지)
async def upload_file_to_openai(file_content: bytes, filename: str) -> FileUploadResponse:
    """
    단일 파일을 OpenAI에 업로드합니다. (호환성 유지)
    
    Args:
        file_content: 파일 내용 (바이트)
        filename: 파일 이름
    
    Returns:
        FileUploadResponse: 업로드 결과
    """
    try:
        # 다중 파일 업로드 함수를 사용
        result = await upload_multiple_files_to_openai([(file_content, filename)])
        
        if result["success"]:
            return FileUploadResponse(
                success=True,
                file_id=result["uploaded_files"][0]["file_id"],
                vector_store_id=result["vector_store_id"]
            )
        else:
            return FileUploadResponse(
                success=False,
                error=result["error"]
            )
            
    except Exception as e:
        print(f"파일 업로드 오류: {str(e)}")
        return FileUploadResponse(
            success=False,
            error=str(e)
        )

# 파일 질의 함수 (Response API로 변경)
async def query_file(request: FileQueryRequest) -> FileQueryResponse:
    """
    파일에 대한 질의를 처리합니다. (Response API 사용)
    
    Args:
        request: 질의 요청 데이터
    
    Returns:
        FileQueryResponse: 질의 결과
    """
    try:
        # 1. 벡터 스토어 ID 체크 또는 생성
        vector_store_id = request.vector_store_id
        
        # vector_store_id가 파일 ID 형식("file-*")인 경우, 벡터 스토어를 생성하고 파일을 추가
        if vector_store_id.startswith("file-"):
            try:
                # 벡터 스토어 생성
                vector_store = client.vector_stores.create(
                    name=f"ChatX Vector Store for {vector_store_id}"
                )
                
                # 벡터 스토어에 파일 추가
                file_batch = client.vector_stores.file_batches.create(
                    vector_store_id=vector_store.id,
                    file_ids=[vector_store_id]
                )
                
                # 새 벡터 스토어 ID 사용
                vector_store_id = vector_store.id
                print(f"새 벡터 스토어 생성 및 파일 추가 완료: {vector_store_id}")
                
                # 파일 처리가 완료될 때까지 잠시 대기
                import time
                time.sleep(5)  # 5초 대기
            except Exception as e:
                print(f"벡터 스토어 생성 중 오류: {str(e)}")
                # 계속 진행 (기존 vector_store_id 사용)
        
        # 2. 대화 히스토리를 포함한 input 메시지 구성
        input_messages = []
        
        # 대화 히스토리가 있으면 추가
        if request.conversation_history:
            for msg in request.conversation_history:
                input_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        else:
            # 대화 히스토리가 없으면 현재 질의만 추가
            input_messages.append({
                "role": "user",
                "content": request.query
            })
        
        # 3. Response API를 사용하여 파일 검색
        # 모델 설정
        model = request.model or "gpt-4o"  # 요청에서 모델을 가져오고, 없으면 기본값 사용
        print(f"파일 질의 모델: 요청={request.model}, 사용={model}")
        
        response = client.responses.create(
            model=model,
            input=input_messages,  # 대화 히스토리 포함
            tools=[{
                "type": "file_search",
                "vector_store_ids": [vector_store_id]
            }],
            include=["file_search_call.results"]  # 지원되는 값만 사용
        )
        
        # 4. 응답 처리
        response_text = ""
        annotations = []
        search_results = []
        file_search_results = {}  # file_id별로 검색 결과를 저장
        
        print(f"Debug - response.output 길이: {len(response.output)}")
        
        # 응답 파싱
        for i, output in enumerate(response.output):
            print(f"Debug - output {i}: type={getattr(output, 'type', 'unknown')}")
            
            if hasattr(output, 'type'):
                # File search call 타입 처리 (먼저 처리하여 검색 결과 저장)
                if output.type == "file_search_call":
                    print(f"Debug - file_search_call 발견")
                    if hasattr(output, 'results') and output.results:
                        print(f"Debug - search results 개수: {len(output.results)}")
                        for k, result in enumerate(output.results):
                            result_info = {
                                "text": result.text,
                                "score": getattr(result, 'score', 0.0)
                            }
                            if hasattr(result, 'file_id'):
                                result_info["file_id"] = result.file_id
                                # file_id별로 검색 결과 저장
                                if result.file_id not in file_search_results:
                                    file_search_results[result.file_id] = []
                                file_search_results[result.file_id].append(result_info)
                            if hasattr(result, 'filename'):
                                result_info["filename"] = result.filename
                            search_results.append(result_info)
                            print(f"Debug - search_result {k}: file_id={result_info.get('file_id', 'unknown')}, text_length={len(result.text)}, score={result_info.get('score', 0.0)}")
                
                # Message 타입 처리
                elif output.type == "message":
                    if hasattr(output, 'content') and len(output.content) > 0:
                        content_item = output.content[0]
                        if hasattr(content_item, 'text'):
                            response_text = content_item.text
                            print(f"Debug - 응답 텍스트 길이: {len(response_text)}")
                        
                        # 인용 정보 추출
                        if hasattr(content_item, 'annotations'):
                            print(f"Debug - annotations 개수: {len(content_item.annotations)}")
                            for j, annotation in enumerate(content_item.annotations):
                                try:
                                    print(f"Debug - annotation {j}: type={getattr(annotation, 'type', 'unknown')}")
                                    
                                    if hasattr(annotation, 'type') and annotation.type == 'file_citation':
                                        # filename은 model_extra에서 가져오기
                                        filename = getattr(annotation, 'filename', annotation.file_id)
                                        if hasattr(annotation, 'model_extra') and 'filename' in annotation.model_extra:
                                            filename = annotation.model_extra['filename']
                                        
                                        # 실제 검색된 소스 텍스트 찾기
                                        source_text = None
                                        source_score = None
                                        
                                        # 해당 file_id의 검색 결과에서 가장 점수가 높은 것 선택
                                        if annotation.file_id in file_search_results:
                                            best_result = max(file_search_results[annotation.file_id], 
                                                            key=lambda x: x.get('score', 0.0))
                                            source_text = best_result['text']
                                            source_score = best_result.get('score', 0.0)
                                        
                                        # 응답 텍스트에서 해당 위치의 텍스트 추출 (생성된 답변 부분)
                                        generated_quote = None
                                        start_index = getattr(annotation, 'index', 0)
                                        if response_text and start_index < len(response_text):
                                            # index 주변의 텍스트 추출 (50자 정도)
                                            end_index = min(start_index + 50, len(response_text))
                                            context_start = max(0, start_index - 25)
                                            generated_quote = response_text[context_start:end_index]
                                            if context_start > 0:
                                                generated_quote = "..." + generated_quote
                                            if end_index < len(response_text):
                                                generated_quote = generated_quote + "..."
                                        
                                        print(f"Debug - 인용 정보: file_id={annotation.file_id}, filename={filename}, index={start_index}")
                                        print(f"Debug - 생성된 답변 부분: {generated_quote[:100] if generated_quote else 'None'}")
                                        print(f"Debug - 실제 소스 텍스트: {source_text[:10000] if source_text else 'None'}...")
                                        print(f"Debug - 검색 점수: {source_score}")
                                        
                                        annotations.append(FileAnnotation(
                                            type=annotation.type,
                                            index=start_index,
                                            file_id=annotation.file_id,
                                            filename=filename,
                                            quote=source_text,  # 실제 검색된 소스 텍스트 사용
                                            score=source_score
                                        ))
                                except Exception as e:
                                    print(f"annotation 처리 중 오류: {str(e)}")
                                    # 오류가 발생해도 계속 진행
                                    continue
        
        return FileQueryResponse(
            response=response_text,
            annotations=annotations,
            search_results=search_results
        )
        
    except Exception as e:
        print(f"파일 질의 오류: {str(e)}")
        return FileQueryResponse(
            response=f"파일 질의 중 오류가 발생했습니다: {str(e)}",
            error=str(e)
        ) 