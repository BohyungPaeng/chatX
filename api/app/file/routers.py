from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List

from .models import FileUploadResponse, FileQueryRequest, FileQueryResponse, MultiFileUploadResponse, FileUploadResult
from .services import upload_file_to_openai, upload_multiple_files_to_openai, query_file

router = APIRouter()


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