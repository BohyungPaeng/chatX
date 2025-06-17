from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .chat.routers import router as chat_router
from .core.database import engine, Base
from .core.logger import logger
from .file.routers import router as file_router
from .image.routers import router as image_router
from .websearch.routers import router as websearch_router

# FastAPI 애플리케이션 생성
app = FastAPI(
    title="GPT-4.1 API",
    description="OpenAI GPT-4.1 모델을 사용한 채팅 API",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 데이터베이스 테이블 생성"""
    from sqlalchemy import text
    
    try:
        async with engine.begin() as conn:
            # 먼저 테이블들을 생성
            await conn.run_sync(Base.metadata.create_all)
            
            # alembic_version 테이블이 없다면 생성하고 현재 버전 설정
            result = await conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'alembic_version'
                );
            """))
            
            table_exists = result.scalar()
            
            if not table_exists:
                # alembic_version 테이블 생성
                await conn.execute(text("""
                    CREATE TABLE alembic_version (
                        version_num VARCHAR(32) NOT NULL,
                        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                    );
                """))
                
                # 현재 마이그레이션 버전 설정
                await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('001');"))
                logger.info("✅ 데이터베이스 테이블과 Alembic 버전이 생성되었습니다.")
            else:
                logger.info("✅ 데이터베이스가 이미 설정되어 있습니다.")
                
    except Exception as e:
        logger.error(f"❌ 데이터베이스 초기화 중 오류: {e}")
        # 실패해도 서버는 계속 실행

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 프로덕션에서는 출처를 명시적으로 지정해야 합니다.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(chat_router, prefix="/api", tags=["Chat"])
app.include_router(image_router, prefix="/api", tags=["Image"])
app.include_router(file_router, prefix="/api", tags=["File"])
app.include_router(websearch_router, prefix="/api", tags=["Web Search"])

# 기본 경로
@app.get("/")
async def root():
    return {
        "message": "GPT-4.1 API 서버가 실행 중입니다.",
        "docs_url": "/docs",
        "endpoints": {
            "chat": "/api/chat",
            "models": "/api/models"
        }
    }