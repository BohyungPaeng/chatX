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

def get_latest_migration_version():
    """alembic/versions 폴더에서 최신 마이그레이션 버전 감지"""
    try:
        import os
        import glob
        
        # versions 폴더 경로
        versions_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic", "versions")
        
        if not os.path.exists(versions_path):
            return "001"  # 기본값
        
        # .py 파일들 찾기
        migration_files = glob.glob(os.path.join(versions_path, "*.py"))
        
        if not migration_files:
            return "001"  # 기본값
        
        # 파일명에서 버전 추출 (예: 003_remove_is_archived.py -> 003)
        versions = []
        for file_path in migration_files:
            filename = os.path.basename(file_path)
            if filename != "__pycache__" and filename.endswith(".py"):
                # 파일명 패턴: 001_xxx.py, 002_xxx.py, 003_xxx.py
                version_part = filename.split("_")[0]
                if version_part.isdigit():
                    versions.append(version_part)
                elif len(version_part) == 12 and version_part.isalnum():  # alembic 기본 형식 (5c5deb7b4002)
                    # 파일 내용에서 revision 읽기
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if "revision = '" in content:
                                revision_line = [line for line in content.split('\n') if "revision = '" in line][0]
                                revision = revision_line.split("'")[1]
                                if revision.isdigit():
                                    versions.append(revision)
                    except:
                        continue
        
        if versions:
            # 숫자 버전들을 정렬해서 최신 버전 반환
            numeric_versions = [v for v in versions if v.isdigit()]
            if numeric_versions:
                return max(numeric_versions, key=int)
        
        return "003"  # 현재 최신 버전
        
    except Exception as e:
        logger.warning(f"⚠️ 마이그레이션 버전 감지 실패: {e}")
        return "003"  # fallback

async def run_migrations():
    """서버 시작시 Alembic 마이그레이션 자동 실행"""
    try:
        from alembic.config import Config
        from alembic import command
        import os
        
        # alembic.ini 파일 경로 설정
        alembic_cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini")
        
        if os.path.exists(alembic_cfg_path):
            alembic_cfg = Config(alembic_cfg_path)
            command.upgrade(alembic_cfg, "head")
            logger.info("✅ 데이터베이스 마이그레이션 자동 적용 완료")
        else:
            logger.warning("⚠️ alembic.ini 파일을 찾을 수 없습니다. 마이그레이션을 건너뜁니다.")
            
    except Exception as e:
        logger.error(f"❌ 마이그레이션 실패: {e}")
        # 마이그레이션 실패해도 서버는 계속 실행
        logger.warning("⚠️ 마이그레이션 실패했지만 서버는 계속 실행됩니다.")

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 자동 마이그레이션 및 데이터베이스 초기화"""
    from sqlalchemy import text
    
    try:
        # 1️⃣ 먼저 Alembic 마이그레이션 실행
        await run_migrations()
        
        # 2️⃣ 기본 테이블 생성 (마이그레이션으로 처리되지 않는 경우 대비)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
            # alembic_version 테이블 확인 및 초기화
            result = await conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'alembic_version'
                );
            """))
            
            table_exists = result.scalar()
            
            if not table_exists:
                # alembic_version 테이블 생성 (마이그레이션이 실행되지 않은 경우)
                await conn.execute(text("""
                    CREATE TABLE alembic_version (
                        version_num VARCHAR(32) NOT NULL,
                        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                    );
                """))
                
                # 최신 버전으로 설정 (동적 감지)
                latest_version = get_latest_migration_version()
                await conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{latest_version}');"))
                logger.info(f"✅ Alembic 버전 테이블이 생성되었습니다. (최신 버전: {latest_version})")
            
            logger.info("✅ 데이터베이스 초기화 완료")
                
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