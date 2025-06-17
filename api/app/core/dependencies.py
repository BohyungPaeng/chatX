import openai
import httpx
import ssl
from .config import OPENAI_API_KEY

# 🔒 SSL 설정 (회사 환경용)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 🌐 HTTP 클라이언트 설정
http_client = httpx.Client(verify=False)

# 🤖 OpenAI 클라이언트 설정 (필요할 때마다 직접 사용)
def get_openai_client():
    return openai.OpenAI(
        api_key=OPENAI_API_KEY,
        http_client=httpx.Client(verify=False),
        max_retries=3,
        timeout=60.0
    )