from openai import OpenAI
import os
import sys
import httpx
import ssl
from openai import APIConnectionError

# 현재 디렉토리를 api 디렉토리로 가정하고 상대 경로 설정
sys.path.append('.')
from app.config import OPENAI_API_KEY

# SSL 인증서 검증 비활성화
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 클라이언트 생성
client = OpenAI(
    api_key=OPENAI_API_KEY,
    http_client=httpx.Client(verify=False),
    timeout=60.0,
    max_retries=3
)

# 파일 ID 또는 파일 ID 목록 - 이미 업로드된 파일이 있는 경우 해당 ID 사용
file_id = "file-abc123"  # 실제 파일 ID로 변경 필요

try:
    print("OpenAI Responses API 파일 검색 테스트 중...")
    
    # 1. 파일이 없는 경우 먼저 업로드
    if file_id == "file-abc123":  # 기본값이 변경되지 않은 경우
        print("파일 업로드 중...")
        # 테스트 파일 생성
        with open("test_file.txt", "w") as f:
            f.write("이것은 테스트 파일입니다. 이 파일에는 중요한 정보가 포함되어 있습니다.")
            
        # 파일 업로드
        with open("test_file.txt", "rb") as f:
            upload_response = client.files.create(
                file=f,
                purpose="assistants"
            )
            file_id = upload_response.id
            print(f"파일 업로드 성공! 파일 ID: {file_id}")
    
    # 2. Responses API로 파일 검색
    print(f"파일 ID '{file_id}'로 검색 중...")
    response = client.responses.create(
        model="gpt-4o",
        input="이 파일에 포함된 정보는 무엇인가요?",
        tools=[{
            "type": "file_search",
            "vector_store_ids": [file_id]
        }],
        include=["file_search_call.results"]
    )
    
    print("파일 검색 성공!")
    print(f"응답 ID: {response.id}")
    
    # 3. 응답 결과 파싱
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