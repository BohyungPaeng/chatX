import openai
import httpx
import ssl
import os
from pathlib import Path
from typing import List, Dict

from ..core.config import OPENAI_API_KEY
from .models import FileUploadResponse, FileQueryRequest, FileQueryResponse, FileAnnotation

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
        model = request.model or "azure.gpt-4.1"  # 요청에서 모델을 가져오고, 없으면 기본값 사용
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
                                        print(f"Debug - 실제 소스 텍스트: {source_text[:100] if source_text else 'None'}...")
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
        from ..retriever.doc_chunker import DocumentChunker
        
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
    
    