import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv(override=True)

# OpenAI API 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# PWC GPT API 설정
LITELLM_URL = os.getenv("LITELLM_URL", "https://genai-sharedservice-americas.pwcinternal.com")
LITELLM_KEY = os.getenv("LITELLM_KEY", "")

# 서버 설정
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# GPT 모델 설정
GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4-1106-preview")
IMAGE_GEN_MODEL = os.getenv("IMAGE_GEN_MODEL", "dall-e-3")
FLAG_LIGHTWEIGHT = True

# 🔧 타임아웃 관련 환경변수 추가
PDF_PROCESSING_TIMEOUT = int(os.getenv("PDF_PROCESSING_TIMEOUT", "30"))
PDF_BATCH_SIZE = int(os.getenv("PDF_BATCH_SIZE", "1"))
PDF_MAX_FILE_SIZE = int(os.getenv("PDF_MAX_FILE_SIZE_MB", "50")) * 1024 * 1024 # 기본 50MB