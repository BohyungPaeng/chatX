import httpx
import os
import sys
import ssl

sys.path.append('.')
from app.config import OPENAI_API_KEY

print("Network connectivity test")

try:
    # SSL 컨텍스트 생성 (인증서 검증 건너뛰기)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    # 기본 HTTP 요청
    print("Testing basic HTTP connectivity...")
    with httpx.Client(timeout=10.0, verify=False) as client:
        response = client.get("https://httpbin.org/get")
        print(f"HTTP Status: {response.status_code}")
        print(f"Response: {response.text[:100]}...")
        
    # OpenAI API 요청
    print("\nTesting OpenAI API connectivity...")
    with httpx.Client(timeout=20.0, verify=False) as client:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        response = client.get("https://api.openai.com/v1/models", headers=headers)
        print(f"OpenAI Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Available models: {len(response.json()['data'])}")
        else:
            print(f"Error: {response.text}")
            
except httpx.ConnectError as e:
    print(f"Connection error: {str(e)}")
    
except Exception as e:
    print(f"Error: {type(e).__name__}: {str(e)}") 