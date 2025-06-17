from openai import OpenAI
import os
import sys
import httpx
import ssl
from openai import APIConnectionError

# 현재 디렉토리를 api 디렉토리로 가정하고 상대 경로 설정
sys.path.append('.')
from app.core.config import OPENAI_API_KEY

# SSL 인증서 검증 비활성화
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 타임아웃 값을 늘려서 클라이언트 생성
client = OpenAI(
    api_key=OPENAI_API_KEY,
    http_client=httpx.Client(verify=False),
    timeout=60.0,  # 기본값보다 더 긴 타임아웃 설정
    max_retries=3
)

try:
    # Responses API 호출 테스트
    print("OpenAI Responses API 연결 테스트 중...")
    response = client.responses.create(
        model="gpt-4o",
        input="Tell me a quick joke"
    )
    print("Responses API 연결 성공!")
    print(f"응답 ID: {response.id}")
    print(f"응답 내용: {response.output[0].content[0].text}")
    
except APIConnectionError as e:
    print(f"OpenAI API 연결 오류: {str(e)}")
    # 상세 오류 정보 출력
    if hasattr(e, "request"):
        print(f"요청 URL: {e.request.url}")
    
except httpx.ConnectError as e:
    print(f"HTTPX 연결 오류: {str(e)}")
    
except Exception as e:
    print(f"일반 오류: {type(e).__name__}: {str(e)}") 