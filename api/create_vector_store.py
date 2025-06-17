from openai import OpenAI
import os
import sys
import httpx
import ssl
from openai import APIConnectionError
import time

# 현재 디렉토리를 api 디렉토리로 가정하고 상대 경로 설정
sys.path.append('.')
from app.core.config import OPENAI_API_KEY

# SSL 인증서 검증 비활성화
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# OpenAI 클라이언트 생성
client = OpenAI(
    api_key=OPENAI_API_KEY,
    http_client=httpx.Client(verify=False),
    timeout=60.0,
    max_retries=3
)

try:
    print("OpenAI 벡터 스토어 생성 테스트 중...")
    
    # 벡터 스토어 생성
    vector_store = client.vector_stores.create(
        name="ChatX Vector Store"
    )
    
    print(f"벡터 스토어 생성 성공!")
    print(f"벡터 스토어 ID: {vector_store.id}")
    print(f"벡터 스토어 이름: {vector_store.name}")
    print(f"생성 시간: {vector_store.created_at}")
    
    # 파일 준비 (테스트 파일 생성)
    print("\n테스트 파일 생성 중...")
    with open("test_file.txt", "w") as f:
        f.write("이것은 벡터 스토어 테스트 파일입니다. 이 파일에는 중요한 정보가 포함되어 있습니다.")
    
    # 파일 업로드
    print("파일 업로드 중...")
    with open("test_file.txt", "rb") as f:
        uploaded_file = client.files.create(
            file=f,
            purpose="assistants"
        )
    
    print(f"파일 업로드 성공! 파일 ID: {uploaded_file.id}")
    
    # 벡터 스토어에 파일 추가
    print(f"\n벡터 스토어 '{vector_store.id}'에 파일 추가 중...")
    file_batch = client.vector_stores.file_batches.create(
        vector_store_id=vector_store.id,
        file_ids=[uploaded_file.id]
    )
    
    print(f"파일 배치 생성 성공! 배치 ID: {file_batch.id}")
    print(f"상태: {file_batch.status}")
    
    # 벡터 스토어 파일 목록 조회
    print(f"\n벡터 스토어 '{vector_store.id}'의 파일 목록 조회 중...")
    files = client.vector_stores.files.list(
        vector_store_id=vector_store.id
    )
    
    print(f"파일 목록 조회 성공!")
    for file in files.data:
        print(f"- 파일 ID: {file.id}, 파일 속성: {file}")
    
    # 파일로 벡터 스토어 검색 테스트
    print(f"\n벡터 스토어 검색 테스트 중...")
    response = client.responses.create(
        model="gpt-4o",
        input="이 파일에 포함된 정보는 무엇인가요?",
        tools=[{
            "type": "file_search",
            "vector_store_ids": [vector_store.id]
        }],
        include=["file_search_call.results"]
    )
    
    print("검색 성공!")
    print(f"응답 ID: {response.id}")
    
    # 응답 결과 파싱
    for output in response.output:
        if hasattr(output, 'type'):
            # 메시지 출력
            if output.type == "message" and hasattr(output, 'content'):
                for content in output.content:
                    if hasattr(content, 'text'):
                        print(f"\n응답 내용: {content.text}")
            
            # 검색 결과 출력
            elif output.type == "file_search_call" and hasattr(output, 'search_results'):
                print("\n파일 검색 결과:")
                for result in output.search_results:
                    print(f"- {result.text}")
    
    # 파일 처리가 완료될 때까지 대기 (필요에 따라)
    print("\n파일 처리가 완료될 때까지 잠시 대기 중...")
    time.sleep(10)  # 10초 대기
    
except APIConnectionError as e:
    print(f"OpenAI API 연결 오류: {str(e)}")
    if hasattr(e, "request"):
        print(f"요청 URL: {e.request.url}")
    
except httpx.ConnectError as e:
    print(f"HTTPX 연결 오류: {str(e)}")
    
except Exception as e:
    print(f"일반 오류: {type(e).__name__}: {str(e)}")
    
finally:
    # 테스트 파일 정리
    if os.path.exists("test_file.txt"):
        os.remove("test_file.txt")
        print("테스트 파일 삭제 완료") 