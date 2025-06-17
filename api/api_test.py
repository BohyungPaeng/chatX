from openai import OpenAI
import os
import sys
import httpx
from openai import APIConnectionError

# 현재 디렉토리를 api 디렉토리로 가정하고 상대 경로 설정
sys.path.append('.')
from app.core.config import OPENAI_API_KEY

print(f"API 키: {OPENAI_API_KEY[:5]}{'*' * 10}")

client = OpenAI(
    api_key=OPENAI_API_KEY,
    timeout=60.0  # 타임아웃 증가
)

try:
    # 간단한 API 호출 테스트
    print("OpenAI API 연결 테스트 중...")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, are you working?"}],
        max_tokens=50
    )
    print("API 연결 성공!")
    print(f"응답: {response.choices[0].message.content}")
    
except APIConnectionError as e:
    print(f"OpenAI API 연결 오류: {str(e)}")
    # 상세 오류 정보 출력
    if hasattr(e, "request"):
        print(f"요청 URL: {e.request.url}")
    
except httpx.ConnectError as e:
    print(f"HTTPX 연결 오류: {str(e)}")
    
except Exception as e:
    print(f"일반 오류: {type(e).__name__}: {str(e)}") 