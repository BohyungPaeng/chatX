import logging
import sys
import colorlog

def setup_logger(sql_debug=False):
    
    # 컬러 로그 포맷 설정
    color_format = (
        "%(log_color)s%(asctime)s%(reset)s "
        "%(log_color)s%(levelname)-8s%(reset)s "
        "%(purple)s%(name)-10s%(reset)s : "
        "%(log_color)s%(message)s%(reset)s"
    )
    
    # 컬러 핸들러 생성
    handler = colorlog.StreamHandler(sys.stdout)
    handler.setFormatter(colorlog.ColoredFormatter(
        color_format,
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green', 
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        },
        secondary_log_colors={},
        style='%'
    ))
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.handlers.clear()  # 기존 핸들러 제거
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    
    # SQLAlchemy 로거 설정
    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    sqlalchemy_logger.handlers.clear()
    if sql_debug:
        sqlalchemy_logger.addHandler(handler)
        sqlalchemy_logger.setLevel(logging.INFO)
    else:
        sqlalchemy_logger.setLevel(logging.WARNING)  # 경고 이상만 출력
    sqlalchemy_logger.propagate = False  # 중복 출력 방지
    
    # Alembic 로거도 설정
    alembic_logger = logging.getLogger("alembic")
    alembic_logger.handlers.clear() 
    alembic_logger.addHandler(handler)
    alembic_logger.setLevel(logging.INFO)
    alembic_logger.propagate = False
    
    # FastAPI 앱용 로거 생성
    logger = logging.getLogger("chatx")
    logger.setLevel(logging.INFO)
    
    return logger

# 전역 로거 인스턴스 (SQLAlchemy 로그는 기본적으로 끔)
logger = setup_logger(sql_debug=False)