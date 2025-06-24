from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List

from .models import FileUploadResponse, FileQueryRequest, FileQueryResponse, MultiFileUploadResponse, FileUploadResult
from .services import upload_file_to_openai, upload_multiple_files_to_openai, query_file

router = APIRouter()

from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File, Form
from ..chat.models import ChatRequest, ChatMessage
from ..chat.services import generate_chat_response, generate_streaming_response
from .services import chunk_pdf_document
from fastapi.responses import StreamingResponse
from typing import List, Optional, AsyncGenerator

import json

router = APIRouter()

from ..config import PDF_BATCH_SIZE, PDF_PROCESSING_TIMEOUT, PDF_MAX_FILE_SIZE, FLAG_EXPERIMENT
from .cache_manager import pdf_cache_manager, get_combined_text_from_cache  # 직접 import
from .pdf_processor import enhanced_pdf_validation, extract_text_from_readable_pdf, PDFBatchProcessor

class GlobalCacheAdapter:
    def __contains__(self, filename):
        return pdf_cache_manager.exists(filename)
    
    def __getitem__(self, filename):
        return pdf_cache_manager.load(filename)
    
    def __setitem__(self, filename, data):
        pdf_cache_manager.save(filename, data)

GLOBAL_PDF_CACHE = GlobalCacheAdapter()

# 🎯 간단한 통합 PDF Streaming + Cache 함수
async def pdf_streaming_with_cache(
    filename: str,
    model: str,
    pdf_content: bytes = None,
    is_readable: bool = True
):
    """Readable/Non-Readable PDF 통합 처리"""
    
    processor = PDFBatchProcessor(pdf_content, filename, model) # readable이 True인 경우만 pdf_content 사용 
    try:
        page_texts = []
        chunk_count = 0
        
        print(f"🔄 PDF streaming ({'readable' if is_readable else 'image'}) for: {filename}")
        
        if is_readable:
            # Readable PDF 처리
            import time
            
            extracted_pages = extract_text_from_readable_pdf(pdf_content, filename)
            if not extracted_pages:
                yield f"data: {json.dumps({'content': '❌ 텍스트 추출 실패', 'is_streaming': False, 'model': model})}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            # 페이지별 스트리밍
            for page in extracted_pages:
                if page.get('text_content', '').strip():
                    chunk_count += 1
                    page_text = f"## 📄 페이지 {page['page_number']}\n\n{page['text_content']}"
                    page_texts.append(page_text)
                    
                    print(f"📦 RAW[{chunk_count}]: {len(page_text)}chars | {page_text[:100]}...")
                    print(f"📄 Page found in chunk {chunk_count}: {len(page_text)}chars")
                    
                    yield f"data: {json.dumps({'content': page_text, 'is_streaming': True, 'model': model})}\n\n"
                    time.sleep(0.05)
        else:
            # Image Processing PDF 처리  
            for raw_text_chunk in processor.process_pdf_streaming():
                chunk_count += 1
                print(f"📦 RAW[{chunk_count}]: {len(raw_text_chunk)}chars | {raw_text_chunk[:100]}...")
                
                yield f"data: {json.dumps({'content': raw_text_chunk, 'is_streaming': True, 'model': processor.model_name})}\n\n"
                
                if "## 📄 페이지" in raw_text_chunk:
                    print(f"📄 Page found in chunk {chunk_count}: {len(raw_text_chunk)}chars")
                    page_texts.append(raw_text_chunk)
        
        # 캐시 저장
        if page_texts:
            cache_data = {
                'page_texts': page_texts,
                'total_pages': len(page_texts),
                'filename': filename,
                'processing_method': 'direct_text_extraction' if is_readable else 'image_ocr_streaming'
            }
            pdf_cache_manager.save(filename, cache_data)
            print(f"💾 Cache: {filename} -> {len(page_texts)} pages")
            
            # combined_text 검증
            combined = get_combined_text_from_cache(filename)
            print(f"✅ Combined: {len(combined)} chars")
            
            final_notice = {"content": "", "is_streaming": False, "cached": True, "pages_found": len(page_texts)}
        else:
            final_notice = {"content": "", "is_streaming": False, "cached": False, "error": "no_pages_found"}
        
        yield f"data: {json.dumps(final_notice)}\n\n"
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        print(f"💥 Error: {str(e)}")
        yield f"data: {json.dumps({'content': f'❌ 오류: {str(e)}', 'is_streaming': False, 'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


@router.post("/process-pdf-batch")
def process_pdf_in_batches(
    file: UploadFile = File(...),
    prompt: str = Form("PDF 문서를 분석해주세요."),
    model: str = Form("azure.gpt-4o-2024-11-20"),
    force_image_processing: bool = Form(False),
    stream: bool = Form(True)
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
        force_image_processing = False
        # #TODO: UI에서 readable이어도 필요시 force image를 True로 켤수있는 선택지를 먼저 물어봐야
        # # 1. 캐시 체크 (force 옵션이 아닐 때만)
        # if not force_image_processing and pdf_cache_manager.exists(file.filename):
        #     print(f"✅ 캐시 hit: {file.filename}")
        #     cache_data = pdf_cache_manager.load(file.filename)
        #     return {
        #         "status": "cached",
        #         "filename": file.filename,
        #         "processing_method": cache_data.get("processing_method", "unknown"),
        #         "cached": True,
        #         "total_pages": cache_data.get("total_pages", 0)
        #     } #FIXME: stream=True라도, False일때처럼한번에 반환하여 프론트 연동이 되지않음 차후 ui작업 시 한번에 처리

        # 파일 내용 읽기
        pdf_content = file.file.read()
        print(f"PDF content loaded: {len(pdf_content)} bytes")

        # PDF 처리 방식 결정
        is_readable = False
        if not force_image_processing:
            validation = enhanced_pdf_validation(pdf_content)

            if not validation['is_valid']:
                raise HTTPException(
                    status_code=400, 
                    detail=f"PDF 파일이 유효하지 않습니다: {validation.get('error', 'Unknown error')}"
                )

            is_readable = validation['is_readable']
            print(f"PDF validation: readable={is_readable}, score={validation.get('language_score', 'N/A')}")

        if stream:
            # 🆕 통합 함수 사용
            if is_readable:
                print("Using readable PDF streaming")
                return StreamingResponse(
                    pdf_streaming_with_cache(
                        filename=file.filename,
                        model=model,
                        pdf_content=pdf_content
                    ),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "Content-Type": "text/event-stream"
                    }
                )
            else:
                print("Using image processing PDF streaming")
                
                return StreamingResponse(
                    pdf_streaming_with_cache(
                        filename=file.filename,
                        model=model,
                        pdf_content=pdf_content,
                        is_readable = False
                    ),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "Content-Type": "text/event-stream"
                    }
                )
        else:
            # 일반 처리 (기존 로직 유지)
            if is_readable:
                extracted_pages = extract_text_from_readable_pdf(pdf_content, file.filename)
                processing_method = "direct_text_extraction"
            else:
                processor = PDFBatchProcessor(pdf_content, file.filename, model)
                extracted_pages, completed = processor.process_pdf_in_batches()
                processing_method = "image_ocr_extraction"

            if not extracted_pages:
                raise HTTPException(status_code=500, detail="PDF 텍스트 추출에 실패했습니다.")

            combined_text = "\n\n".join([
                f"=== 페이지 {page['page_number']} ===\n{page['text_content']}"
                for page in extracted_pages
                if page.get('text_content', '').strip()
            ])
            
            data = {
                'page_texts': [page.get('text_content', '') for page in extracted_pages if page.get('text_content', '').strip()],
                'total_pages': len(extracted_pages),
                'filename': file.filename,
                'processing_method': processing_method
            }
            pdf_cache_manager.save(file.filename, data)
            
            print(f"Cached {processing_method} PDF: {len(extracted_pages)} pages")

            return {
                "status": "completed" if is_readable or completed else "partial",
                "filename": file.filename,
                "processing_method": processing_method,
                "cached": True
            }
                
    except HTTPException:
        raise
    except Exception as e:
        print(f"Critical error in PDF processing: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF 처리 중 오류: {str(e)}")

@router.post("/chat-with-pdf")
async def chat_with_pdf(
    filename: str = Form(...),
    prompt: str = Form(...),
    master_system_prompt: str = Form(""),  # 🆕 추가
    model: str = Form("azure.gpt-4o-2024-11-20"),
    stream: bool = Form(True)
):
    """
    글로벌 캐시에서 PDF 텍스트를 가져와서 채팅 응답 생성
    """
    from ..retriever.rag_engine import SearchIndex, search_and_generate_system_message, search_with_faiss_engine, _ensemble_faiss_tfidf    
    import time
    try:
        print(f"=== Chat with PDF Started ===")
        print(f"Filename: {filename}, Model: {model}, Stream: {stream}")
        
        # 글로벌 캐시에서 텍스트 가져오기
        if filename not in GLOBAL_PDF_CACHE:
            raise HTTPException(status_code=400, detail="PDF 텍스트를 찾을 수 없습니다. 먼저 PDF를 분석해주세요.")
        
        extracted_text = get_combined_text_from_cache(filename)
        print(f"Found cached text length: {len(extracted_text)}")

        start_time = time.time()
        system_message, search_results = search_with_faiss_engine(filename, prompt, top_k=5)
        
        search_time_ms = (time.time() - start_time) * 1000
        print(search_time_ms, " 검색에 소요되었습니다")
        
        from ..retriever.rag_monitor_phoenix import auto_monitor_chat
        auto_monitor_chat(prompt, filename, search_results, search_time_ms)
        
        tfidf_weight = 0.3
        K = 5
        if tfidf_weight > 0.0 or FLAG_EXPERIMENT:
            
            chunks = GLOBAL_PDF_CACHE[filename].get('semantic_chunks', [])
            if not chunks:
                # 🔧 청킹 시도 - 실패해도 기존 방식으로 진행
                chunks = await chunk_pdf_document(filename)
                GLOBAL_PDF_CACHE[filename]['semantic_chunks'] = chunks

            print(f"Using cached {len(chunks)} chunks")
            # 🆕 통합 검색 및 시스템 메시지 생성 (페이지 컨텍스트 모드)
            search_index = SearchIndex(chunks)
            _, tfidf_results = search_and_generate_system_message(search_index, prompt, filename, use_page_context=True, top_k=K)
            auto_monitor_chat(prompt, filename, tfidf_results, search_time_ms, method = "retrieve/tfidf")
                
            if tfidf_results:
                # 앙상블 수행
                search_results = _ensemble_faiss_tfidf(search_results, tfidf_results, tfidf_weight, K)
                print(f"✅ FAISS + TF-IDF 앙상블 완료: {len(search_results)}개 최종 결과")
            else:
                print("⚠️ TF-IDF 결과 없음, FAISS만 사용")
                search_results = search_results[:K]
        # 마스터 시스템 프롬프트가 있으면 병합
        if master_system_prompt:
            system_message = f"{master_system_prompt}\n\n{system_message}"    
            print("설정된 SYSTEM_PROMPT:", system_message)

        if search_results:
            print(f"🎯 Top-5 검색 결과:")
            for result in search_results:
                print(f"  {result.citation}: {result.score:.3f} - {result.chunk.content[:100]}...")
        else:
            print("⚠️ 검색 결과 없음, 전체 문서 사용")
        
        # ChatRequest 생성
        chat_request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=system_message),
                ChatMessage(role="user", content=prompt)
            ],
            model=model,
            temperature=0,
            max_tokens=4092,
            stream=stream
        )
        if stream:
            # 스트리밍 응답
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
            start_time = time.time()
            
            response = await generate_chat_response(chat_request)
            print(f"🔍 (DEBUG for Non-streaming) PWC Response type: {type(response)}")
            print(f"🔍 PWC Response content: {response}")
            auto_monitor_chat(prompt, filename, search_results, search_time_ms = (time.time() - start_time) * 1000, ai_response=response.response)
            return response
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Critical error in chat with PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF 채팅 중 오류: {str(e)}")
    
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


@router.post("/upload-file", response_model=FileUploadResponse)
async def upload_file_endpoint(file: UploadFile = File(...)):
    """
    파일을 업로드하고 OpenAI API에 저장합니다.
    
    Args:
        file: 업로드된 파일
    
    Returns:
        FileUploadResponse: 업로드 결과
    """
    try:
        # 파일 검증 - 지원되는 형식인지 확인
        supported_formats = [
            "application/pdf", 
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "text/plain", 
            "text/markdown",
            "text/csv"
        ]
        
        content_type = file.content_type
        print(f"업로드된 파일: {file.filename}, 타입: {content_type}")
        
        if content_type not in supported_formats:
            return FileUploadResponse(
                success=False,
                error=f"지원되지 않는 파일 형식입니다. 지원되는 형식: PDF, DOCX, PPTX, TXT, MD, CSV"
            )
        
        # 파일 크기 검증 (100MB 제한)
        contents = await file.read()
        file_size = len(contents) / (1024 * 1024)  # MB 단위로 변환
        
        print(f"파일 크기: {file_size:.2f}MB")
        
        if file_size > 100:
            return FileUploadResponse(
                success=False,
                error="파일 크기가 너무 큽니다. 최대 100MB까지 지원합니다."
            )
        
        # OpenAI API로 파일 업로드
        result = await upload_file_to_openai(contents, file.filename)
        
        if result.success:
            print(f"파일 업로드 성공: {result.file_id}")
        else:
            print(f"파일 업로드 실패: {result.error}")
        
        return result
        
    except Exception as e:
        error_message = f"파일 업로드 오류: {str(e)}"
        print(error_message)
        return FileUploadResponse(
            success=False,
            error=error_message
        )


@router.post("/query-file", response_model=FileQueryResponse)
async def query_file_endpoint(request: FileQueryRequest):
    """
    업로드된 파일에 대해 질의합니다.
    
    Args:
        request: 질의 요청 데이터
    
    Returns:
        FileQueryResponse: 질의 결과
    """
    try:
        result = await query_file(request)
        return result
    except Exception as e:
        print(f"파일 질의 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-multiple-files", response_model=MultiFileUploadResponse)
async def upload_multiple_files_endpoint(files: List[UploadFile] = File(...)):
    """
    여러 파일을 업로드하고 OpenAI API의 하나의 벡터 스토어에 저장합니다.
    
    Args:
        files: 업로드된 파일 목록
    
    Returns:
        MultiFileUploadResponse: 업로드 결과
    """
    try:
        # 파일 검증 - 지원되는 형식인지 확인
        supported_formats = [
            "application/pdf", 
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "text/plain", 
            "text/markdown",
            "text/csv"
        ]
        
        files_data = []
        results = []
        
        for file in files:
            content_type = file.content_type
            print(f"업로드된 파일: {file.filename}, 타입: {content_type}")
            
            if content_type not in supported_formats:
                results.append(FileUploadResult(
                    filename=file.filename,
                    success=False,
                    error="지원되지 않는 파일 형식입니다. 지원되는 형식: PDF, DOCX, PPTX, TXT, MD, CSV"
                ))
                continue
            
            # 파일 크기 검증 (100MB 제한)
            contents = await file.read()
            file_size = len(contents) / (1024 * 1024)  # MB 단위로 변환
            
            print(f"파일 크기: {file_size:.2f}MB")
            
            if file_size > 100:
                results.append(FileUploadResult(
                    filename=file.filename,
                    success=False,
                    error="파일 크기가 너무 큽니다. 최대 100MB까지 지원합니다."
                ))
                continue
            
            # 유효한 파일 데이터로 추가
            files_data.append((contents, file.filename))
            results.append(FileUploadResult(
                filename=file.filename,
                success=True
            ))
        
        # 유효한 파일들을 하나의 벡터 스토어에 업로드
        if files_data:
            upload_result = await upload_multiple_files_to_openai(files_data)
            
            if upload_result["success"]:
                # 성공한 파일들의 file_id 업데이트
                for i, uploaded_file in enumerate(upload_result["uploaded_files"]):
                    for result in results:
                        if result.filename == uploaded_file["filename"] and result.success:
                            result.file_id = uploaded_file["file_id"]
                            break
                
                return MultiFileUploadResponse(
                    success=True,
                    vector_store_id=upload_result["vector_store_id"],
                    results=results
                )
            else:
                # 업로드 실패 시 모든 결과를 실패로 변경
                for result in results:
                    if result.success:
                        result.success = False
                        result.error = upload_result["error"]
                
                return MultiFileUploadResponse(
                    success=False,
                    results=results,
                    error=upload_result["error"]
                )
        else:
            return MultiFileUploadResponse(
                success=False,
                results=results,
                error="업로드 가능한 파일이 없습니다."
            )
        
    except Exception as e:
        error_message = f"파일 업로드 오류: {str(e)}"
        print(error_message)
        return MultiFileUploadResponse(
            success=False,
            results=[FileUploadResult(
                filename=file.filename,
                success=False,
                error=error_message
            ) for file in files],
            error=error_message
        )