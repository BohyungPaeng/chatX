import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# OpenAI API 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")

# 서버 설정
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# GPT 모델 설정
GPT_MODEL = os.getenv("GPT_MODEL")

# PWC 내부 API용 모델 매핑
MODEL_MAPPING = {
    "gpt-4.1": "azure.gpt-4.1",
    "gpt-4o": "azure.gpt-4o", 
    "o4-mini": "azure.gpt-4o-mini",
    "o3": "azure.o3"
}

# Database 설정
# 로컬 개발용과 배포용 DATABASE_URL 분리
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    # 로컬 개발: localhost
    # 배포 환경: 컨테이너 이름으로 통신
    "postgresql+asyncpg://chatx_user:chatx_password@chatx-postgres:5432/chatx_db"
)

# JWT 설정
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30