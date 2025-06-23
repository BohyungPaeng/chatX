from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from .core.database import Base


class User(Base):

    __tablename__ = "tb_users"
    
    # 기본 정보
    id = Column(Integer, primary_key=True)
    email = Column(String(254), unique=True, nullable=False)  # 이메일 (SSO 로그인용)
    name = Column(String(100))  # 이름
    
    # 설정
    is_active = Column(Boolean, default=True)  # 활성 여부
    
    # 시간
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime)
    
    def __repr__(self):
        return f"<User(email='{self.email}', name='{self.name}')>"


class Conversation(Base):

    __tablename__ = "tb_conversations"
    
    # 기본 정보  
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)  # 어떤 사용자의 대화인지
    title = Column(String(255), default="새로운 대화")  # 대화 제목
    
    # 통계
    message_count = Column(Integer, default=0)  # 메시지 개수
    total_tokens = Column(Integer, default=0)  # 사용한 토큰 수
    
    # 상태
    is_deleted = Column(Boolean, default=False)  # 삭제됨 여부 (soft delete)
    
    # 시간
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Conversation(title='{self.title}', user_id={self.user_id})>"


class Message(Base):
    __tablename__ = "tb_messages"
    
    # 기본 정보
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, nullable=False)  # 어떤 대화의 메시지인지
    user_id = Column(Integer, nullable=False)  # 어떤 사용자의 메시지인지
    
    # 메시지 내용
    question = Column(Text, nullable=False)  # 사용자 질문
    answer = Column(Text)  # AI 답변 (아직 답변이 없으면 비어있음)
    
    # 순서와 상태
    order = Column(Integer, nullable=False)  # 대화 내 순서 (1, 2, 3...)
    status = Column(String(20), default='pending')  # pending(대기중), completed(완료), failed(실패)
    
    # AI 정보
    model_used = Column(String(50))  # 사용한 AI 모델
    question_tokens = Column(Integer, default=0)  # 질문 토큰 수
    answer_tokens = Column(Integer, default=0)  # 답변 토큰 수
    
    # 추가 정보 (JSON 형태로 저장)
    extra_info = Column(Text)  # 파일 첨부, 웹검색 결과 등
    
    # 시간
    question_time = Column(DateTime, default=func.now())  # 질문한 시간
    answer_time = Column(DateTime)  # 답변 완료 시간
    
    def __repr__(self):
        return f"<Message(question='{self.question[:30]}...', status='{self.status}')>"