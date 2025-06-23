import time

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ChatRequest, ConversationTitleRequest
from .services import ChatService
from ..core.database import get_db
from ..core.logger import logger
from ..user.services import UserService

router = APIRouter()

async def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)

async def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(db)


@router.post("/chat")
async def chat_with_ai(
    request: ChatRequest,
    user_service: UserService = Depends(get_user_service),
    chat_service: ChatService = Depends(get_chat_service)
):

    logger.info(f"🌐 [스트리밍 API 시작] 채팅 요청 수신 - 모델: {request.model}")
    
    try:

        user_step_start = time.time()
        user_email = request.user_email or "temp@company.com"
        user, is_new = await user_service.get_or_create_user_by_email(email=user_email)
        user_step_time = time.time() - user_step_start
        logger.info(f"⏱️  [API] 사용자 처리 완료: {user_step_time:.2f}초 (신규: {is_new})")
        

        conversation = None
        if request.conversation_id:
            conversations = await chat_service.get_user_conversations(user.id)
            conversation = next(
                (c for c in conversations if c.id == request.conversation_id), 
                None
            )
        
        if not conversation:
            conversation = await chat_service.create_conversation(
                user_id=user.id,
                title="새로운 대화"
            )
        

        user_message = request.messages[-1].content
        

        message, stream_generator = await chat_service.process_chat_request_streaming(
            user_id=user.id,
            conversation_id=conversation.id,
            user_message=user_message,
            model=request.model
        )
        
        logger.info(f"🚀 [실시간 스트리밍] 스트리밍 응답 시작, message_id={message.id}")
        
        return StreamingResponse(
            stream_generator,
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/plain; charset=utf-8"
            }
        )
        
    except Exception as e:
        import traceback
        error_detail = f"채팅 처리 중 오류가 발생했습니다: {str(e)}"
        logger.error(f"❌ 채팅 오류: {error_detail}")
        logger.error(f"❌ 상세 스택: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )


@router.get("/conversations")
async def get_my_conversations(
    user_email: str = "temp@company.com",  # SSO 구현 전 기본값
    user_service: UserService = Depends(get_user_service),
    chat_service: ChatService = Depends(get_chat_service)
):

    try:
        # 사용자 찾기
        user = await user_service.get_user_by_email(user_email)
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        # 대화 목록 가져오기
        conversations = await chat_service.get_user_conversations(user.id)
        
        return {
            "user_email": user_email,
            "conversations": [
                {
                    "id": conv.id,
                    "title": conv.title,
                    "message_count": conv.message_count,
                    "created_at": conv.created_at,
                    "updated_at": conv.updated_at
                }
                for conv in conversations
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"대화 목록 조회 중 오류: {str(e)}"
        )


@router.get("/conversation/{conversation_id}/messages")
async def get_conversation_history(
    conversation_id: int,
    chat_service: ChatService = Depends(get_chat_service)
):

    try:
        messages = await chat_service.get_conversation_messages(conversation_id)
        
        return {
            "conversation_id": conversation_id,
            "messages": [
                {
                    "id": msg.id,
                    "question": msg.question,
                    "answer": msg.answer,
                    "order": msg.order,
                    "status": msg.status,
                    "question_time": msg.question_time,
                    "answer_time": msg.answer_time
                }
                for msg in messages
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"대화 히스토리 조회 중 오류: {str(e)}"
        )




@router.put("/conversation/{conversation_id}")
async def update_conversation_title(
    conversation_id: int,
    title_request: ConversationTitleRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    ✏️ 대화 제목 수정
    """
    try:
        success = await chat_service.update_conversation_title(
            conversation_id, 
            title_request.title
        )
        
        if success:
            return {
                "message": "대화 제목이 성공적으로 수정되었습니다",
                "conversation_id": conversation_id,
                "title": title_request.title
            }
        else:
            raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"대화 제목 수정 중 오류: {str(e)}"
        )


@router.delete("/conversation/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    🗑️ 대화 삭제 (soft delete)
    """
    try:
        success = await chat_service.delete_conversation(conversation_id)
        
        if success:
            return {
                "message": "대화가 성공적으로 삭제되었습니다",
                "conversation_id": conversation_id,
                "deleted": True
            }
        else:
            raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"대화 삭제 중 오류: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    ✅ API 상태 확인
    """
    return {"status": "healthy", "service": "chat", "architecture": "services + simple db"}