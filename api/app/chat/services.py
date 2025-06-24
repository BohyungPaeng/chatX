import json
import time
from datetime import datetime
from typing import List, Tuple

import httpx
import openai
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import OPENAI_API_KEY, OPENAI_BASE_URL, MODEL_MAPPING
from ..core.database import save_to_db, get_by_id
from ..core.logger import logger
from ..models import Conversation, Message

################################################################
### api/chat-with-pdf/ 
### Legacy 방식의 Chat response 생성함수 
################################################################
import asyncio
from .models import ChatRequest, ChatResponse

client = openai.OpenAI(api_key=OPENAI_API_KEY)
async def _get_pwc_model(model_name: str) -> 'AsyncPwCGPTModel':
    """PWC GPT 모델 인스턴스를 생성하고 헬스체크를 수행합니다."""
    from ..tools.pwc_gpt import AsyncPwCGPTModel
    
    pwc = AsyncPwCGPTModel(default_model_name=model_name)
    status = await pwc.health_check()
    if status != 200:
        print(f"PWC GPT health check failed: {status}")
    return pwc

async def generate_chat_response(request: ChatRequest) -> ChatResponse:
    """
    대화 응답을 생성합니다.
    
    Args:
        request: ChatRequest 모델의 요청 데이터
    
    Returns:
        ChatResponse: 응답 데이터
    """
    try:
        # 모델 설정
        model = request.model or "gpt-4.1"
        
        # 모델 ID 매핑 (필요한 경우)
        model_mapping = {
            "gpt-4.1": "gpt-4.1",
            "gpt-4o": "gpt-4.1",
            "o4-mini": "gpt-4.1",
            "o3": "gpt-3.5-turbo"
        }
        
        # 모델 ID 변환
        api_model = model_mapping.get(model, model)
        
        # 입력 메시지 형식 변환 및 필터링
        input_messages = []
        for msg in request.messages:
            # 일반 모드에서는 이미지 URL이 있는 메시지와 웹 검색 관련 메시지만 제외
            if msg.role == "system" and any(keyword in msg.content for keyword in ["삼일회계법인", "웹 검색:", "검색 결과:"]):
                print(f"Filtering out system message containing search keywords: {msg.content[:30]}...")
                continue
            
            input_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        if model.startswith("azure."):
            pwc = await _get_pwc_model(model)
            # PWC GPT 호출 (OpenAI와 유사하게)
            response = await pwc.run(
                messages=input_messages,
                max_tokens=request.max_tokens,
                model=model
            )
            # response는 dict로 가정 (OpenAI와 유사하게)
            content = response["choices"][0]["message"]["content"]
            usage = response.get("usage", {})
            return ChatResponse(
                response=content,
                model=model,
                usage=usage,
                citations=[]
            )
        else:
            # API 호출 준비
            api_params = {
                "model": api_model,
                "messages": input_messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens
            }
            
            # API 호출            
            response = client.chat.completions.create(**api_params)
            
            # 응답 파싱
            content = response.choices[0].message.content
            
            # 사용량 정보
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            return ChatResponse(
                response=content,
                model=model,
                usage=usage,
                citations=[]
            )
        
    except Exception as e:
        # 에러 처리
        error_message = f"Error generating chat response: {str(e)}"
        print(f"Chat error: {str(e)}")
        return ChatResponse(
            response=error_message,
            model=model,
            usage={"error": str(e)}
        )

async def generate_streaming_response(request: ChatRequest):
    """
    대화 응답을 생성하고 스트리밍 형식으로 반환합니다.
    Args:
        request: ChatRequest 모델의 요청 데이터
    Returns:
        스트리밍 응답 제너레이터
    """
    # 모델 설정
    model = request.model or "gpt-4.1"
    
    # 모델 ID 매핑 (필요한 경우)
    model_mapping = {
        "gpt-4.1": "gpt-4.1",
        "gpt-4o": "gpt-4.1",
        "o4-mini": "gpt-4.1",
        "o3": "gpt-3.5-turbo"
    }
    
    # 모델 ID 변환
    model = model_mapping.get(model, model)
    async def stream_generator():
        try:
            # 입력 메시지 형식 변환 및 필터링
            filtered_messages = []
            # 향후 conversation_history가 추가될 경우 아래 주석을 참고하여 messages를 생성할 수 있습니다.
            # messages = []
            # if hasattr(request, 'conversation_history') and request.conversation_history:
            #     for msg in request.conversation_history:
            #         messages.append({"role": msg.role, "content": msg.content})
            # else:
            #     for msg in request.messages:
            #         messages.append({"role": msg.role, "content": msg.content})
            
            # 특수 필터링 단어 리스트
            filter_keywords = [
                "삼일회계법인", "주소는", "웹 검색:", "검색 결과:", 
                "bizbank.co.kr", "oldee.kr", "ytn.co.kr", "sedaily.com"
            ]
            
            for msg in request.messages:
                # 시스템 메시지 필터링
                if msg.role == "system" and any(keyword in msg.content for keyword in filter_keywords):
                    print(f"Filtering out system message with keywords: {msg.content[:50]}...")
                    continue
                # 사용자 메시지 중 웹 검색 접두사 제거
                if msg.role == "user" and msg.content.startswith("웹 검색:"):
                    msg.content = msg.content.replace("웹 검색:", "").strip()
                filtered_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

            collected_messages = []
            if model.startswith("azure."):
                # PWC GPT 스트리밍
                pwc = await _get_pwc_model(model)
                async for chunk in pwc.run_stream(
                    messages=filtered_messages,
                    max_tokens=request.max_tokens,
                    model=model
                ):
                    if "choices" in chunk and len(chunk["choices"]) > 0:
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            collected_messages.append(content)
                            yield f"data: {json.dumps({'content': content, 'is_streaming': True, 'model': model})}\n\n"
                            await asyncio.sleep(0)
            else:
                # API 호출 준비
                api_params = {
                    "model": model,
                    "messages": filtered_messages,
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "stream": True
                }
                # API 호출
                stream = client.chat.completions.create(**api_params)
                # 청크 스트리밍
                for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        content = chunk.choices[0].delta.content
                        collected_messages.append(content)
                        # 각 청크를 JSON으로 반환
                        yield f"data: {json.dumps({'content': content, 'is_streaming': True, 'model': model})}\n\n"
                        await asyncio.sleep(0)
            # 스트리밍 완료 신호
            completion_info = {
                'content': '', 
                'is_streaming': False, 
                'model': model, 
                'usage': {'completion_tokens': len(collected_messages)}
            }
            yield f"data: {json.dumps(completion_info)}\n\n"
            yield f"data: [DONE]\n\n"
        except Exception as e:
            # 에러 처리
            error_message = f"Error streaming response: {str(e)}"
            print(f"Streaming error: {str(e)}")
            yield f"data: {json.dumps({'content': error_message, 'is_streaming': False, 'error': str(e), 'model': model})}\n\n"
            yield f"data: [DONE]\n\n"
    # 비동기 이터레이터 반환
    return stream_generator()

################################################################

class ChatService:
    
    def __init__(self, db: AsyncSession):
        self.db = db
        # 🤖 OpenAI 클라이언트 설정
        client_config = {
            "api_key": OPENAI_API_KEY,
            "http_client": httpx.Client(verify=False),
            "max_retries": 3,
            "timeout": 60.0
        }
        
        # PWC 내부 API 사용시 base_url 설정
        if OPENAI_BASE_URL:
            client_config["base_url"] = OPENAI_BASE_URL
            
        self.openai_client = openai.OpenAI(**client_config)
    
    async def create_conversation(self, user_id: int, title: str = "새로운 대화") -> Conversation:
        conversation_data = {
            "user_id": user_id,
            "title": title,
            "message_count": 0,
            "total_tokens": 0
        }
        
        conversation = Conversation(**conversation_data)
        return await save_to_db(self.db, conversation)
    
    async def get_user_conversations(self, user_id: int, limit: int = 50) -> List[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .where(Conversation.is_deleted == False)  # 삭제된 대화 제외
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_conversation_messages(self, conversation_id: int) -> List[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.order)
        )
        return result.scalars().all()
    
    async def get_conversation_context(self, conversation_id: int) -> List[dict]:

        messages = await self.get_conversation_messages(conversation_id)
        context = []
        
        for message in messages:
            if message.status == "completed":
                # 사용자 질문 추가
                context.append({"role": "user", "content": message.question})
                # AI 답변 추가
                if message.answer:
                    context.append({"role": "assistant", "content": message.answer})
        
        return context
    
    async def process_chat_request_streaming(self, user_id: int, conversation_id: int, 
                                         user_message: str, model: str = "gpt-4") -> Tuple[Message, any]:
        """
        💬 멀티턴 스트리밍 채팅 요청 처리하기
        
        Args:
            user_id: 사용자 ID
            conversation_id: 대화방 ID  
            user_message: 사용자 질문
            model: 사용할 AI 모델
            
        Returns:
            Tuple[Message, StreamingResponse]: (저장된 메시지 객체, 스트리밍 응답)
        """
        start_time = time.time()
        logger.info(f"🕐 [스트리밍 시작] 멀티턴 채팅 처리 시작 - 사용자: {user_id}, 모델: {model}")
        
        try:
            # 1️⃣ 사용자 질문을 DB에 저장
            step1_start = time.time()
            message = await self._save_user_question(conversation_id, user_id, user_message)
            step1_time = time.time() - step1_start
            logger.info(f"⏱️  [1단계] 사용자 질문 저장 완료: {step1_time:.2f}초")
            
            # 2️⃣ 대화 컨텍스트 조회 (멀티턴 지원)
            context = await self.get_conversation_context(conversation_id)
            # 현재 사용자 메시지 추가
            context.append({"role": "user", "content": user_message})
            
            # 3️⃣ 스트리밍 응답 생성기 생성
            async def streaming_generator():
                collected_content = []
                usage = None
                
                try:
                    # AI 스트리밍 호출
                    stream = await self._ask_openai_streaming(context, model)
                    
                    # 스트리밍 청크 처리
                    for chunk in stream:
                        if chunk.choices[0].delta.content is not None:
                            content = chunk.choices[0].delta.content
                            collected_content.append(content)
                            
                            # 실시간 청크 전송
                            yield f"data: {json.dumps({'content': content, 'is_streaming': True, 'conversation_id': conversation_id, 'message_id': message.id})}\n\n"
                        
                        # 마지막 청크에서 정확한 토큰 사용량 정보 수집
                        if hasattr(chunk, 'usage') and chunk.usage is not None:
                            usage = {
                                "prompt_tokens": chunk.usage.prompt_tokens,
                                "completion_tokens": chunk.usage.completion_tokens,
                                "total_tokens": chunk.usage.total_tokens
                            }
                    
                    # 전체 응답 조합
                    full_response = "".join(collected_content)
                    
                    # 토큰 정보가 없는 경우에만 추정치 사용
                    if usage is None:
                        usage = {
                            "prompt_tokens": len(user_message) // 4,  # 단순 추정 (fallback)
                            "completion_tokens": len(full_response) // 4,
                            "total_tokens": 0
                        }
                        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
                    
                    # 4️⃣ AI 답변을 DB에 저장
                    ai_response = {
                        "content": full_response,
                        "usage": usage
                    }
                    await self._save_ai_answer(message, ai_response, model)
                    
                    # 5️⃣ 대화방 통계 업데이트
                    await self._update_conversation_stats(conversation_id, usage)
                    
                    # 완료 신호 전송
                    yield f"data: {json.dumps({'content': '', 'is_streaming': False, 'conversation_id': conversation_id, 'message_id': message.id, 'usage': usage})}\n\n"
                    yield "data: [DONE]\n\n"
                    
                    total_time = time.time() - start_time
                    logger.info(f"🎉 [스트리밍 완료] 전체 처리 시간: {total_time:.2f}초, message_id={message.id}")
                    
                except Exception as e:
                    # 스트리밍 중 오류 처리
                    await self._mark_message_failed(message.id, str(e))
                    error_msg = f"스트리밍 중 오류: {str(e)}"
                    yield f"data: {json.dumps({'content': error_msg, 'is_streaming': False, 'error': str(e)})}\n\n"
                    yield "data: [DONE]\n\n"
            
            return message, streaming_generator()
            
        except Exception as e:
            # 초기 설정 실패 처리
            if 'message' in locals():
                await self._mark_message_failed(message.id, str(e))
            raise Exception(f"스트리밍 채팅 처리 중 오류가 발생했습니다: {str(e)}")
    
    # async def process_chat_request(self, user_id: int, conversation_id: int,
    #                              user_message: str, model: str = "gpt-4") -> Tuple[Message, str]:
    #     """
    #     💬 멀티턴 채팅 요청 처리하기
    #
    #     Args:
    #         user_id: 사용자 ID
    #         conversation_id: 대화방 ID
    #         user_message: 사용자 질문
    #         model: 사용할 AI 모델
    #
    #     Returns:
    #         Tuple[Message, str]: (저장된 메시지 객체, AI 답변)
    #     """
    #     start_time = time.time()
    #     logger.info(f"🕐 [시작] 멀티턴 채팅 처리 시작 - 사용자: {user_id}, 모델: {model}")
    #
    #     try:
    #         # 1️⃣ 사용자 질문을 DB에 저장
    #         step1_start = time.time()
    #         message = await self._save_user_question(conversation_id, user_id, user_message)
    #         step1_time = time.time() - step1_start
    #         logger.info(f"⏱️  [1단계] 사용자 질문 저장 완료: {step1_time:.2f}초")
    #
    #         # 2️⃣ 대화 컨텍스트 조회 및 AI 호출 (멀티턴 지원)
    #         step2_start = time.time()
    #         context = await self.get_conversation_context(conversation_id)
    #         # 현재 사용자 메시지 추가
    #         context.append({"role": "user", "content": user_message})
    #         logger.info(f"🤖 [AI 호출 시작] 모델: {model} → 매핑: {MODEL_MAPPING.get(model, model)}, 컨텍스트: {len(context)}개 메시지")
    #         ai_response = await self._ask_openai(context, model)
    #         step2_time = time.time() - step2_start
    #         logger.info(f"⏱️  [2단계] AI 응답 완료: {step2_time:.2f}초, 응답 길이: {len(ai_response['content'])}자")
    #
    #         # 3️⃣ AI 답변을 DB에 저장
    #         step3_start = time.time()
    #         logger.info(f"🔄 AI 답변 저장 중... 내용: {ai_response['content'][:100]}...")
    #         await self._save_ai_answer(message, ai_response, model)
    #         step3_time = time.time() - step3_start
    #         logger.info(f"⏱️  [3단계] AI 답변 저장 완료: {step3_time:.2f}초")
    #
    #         # 4️⃣ 대화방 통계 업데이트
    #         step4_start = time.time()
    #         await self._update_conversation_stats(conversation_id, ai_response.get("usage", {}))
    #         step4_time = time.time() - step4_start
    #         logger.info(f"⏱️  [4단계] 대화방 통계 업데이트 완료: {step4_time:.2f}초")
    #
    #         total_time = time.time() - start_time
    #         logger.info(f"🎉 [완료] 전체 처리 시간: {total_time:.2f}초, message_id={message.id}")
    #         logger.info(f"📊 시간 분석: DB저장({step1_time:.2f}s) + AI호출({step2_time:.2f}s) + 답변저장({step3_time:.2f}s) + 통계({step4_time:.2f}s)")
    #
    #         return message, ai_response["content"]
    #
    #     except Exception as e:
    #         # ❌ 실패 처리
    #         if 'message' in locals():
    #             await self._mark_message_failed(message.id, str(e))
    #         raise Exception(f"채팅 처리 중 오류가 발생했습니다: {str(e)}")
    
    async def _save_user_question(self, conversation_id: int, user_id: int, question: str) -> Message:
        """📝 사용자 질문 저장하기"""
        # 다음 순서 번호 계산
        result = await self.db.execute(
            select(func.max(Message.order)).where(Message.conversation_id == conversation_id)
        )
        max_order = result.scalar() or 0
        next_order = max_order + 1
        
        # 메시지 저장
        message_data = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "question": question,
            "order": next_order,
            "status": "pending"
        }
        
        message = Message(**message_data)
        return await save_to_db(self.db, message)
    
    # async def _ask_openai(self, messages: List[dict], model: str = "gpt-4.1") -> dict:
    #     """🤖 OpenAI API 호출하기 (비스트리밍)"""
    #     # 모델 매핑 적용
    #     mapped_model = MODEL_MAPPING.get(model, model)
    #
    #     # 🔍 웹 검색 관련 메시지 필터링 (이전 검색 결과 제거)
    #     filtered_messages = self._filter_messages(messages)
    #
    #     response = self.openai_client.chat.completions.create(
    #         model=mapped_model,
    #         messages=filtered_messages,
    #         temperature=0.7,
    #         max_tokens=1000
    #     )
    #
    #     return {
    #         "content": response.choices[0].message.content,
    #         "usage": {
    #             "prompt_tokens": response.usage.prompt_tokens,
    #             "completion_tokens": response.usage.completion_tokens,
    #             "total_tokens": response.usage.total_tokens
    #         }
    #     }
    
    async def _ask_openai_streaming(self, messages: List[dict], model: str = "gpt-4.1"):
        """🚀 OpenAI API 스트리밍 호출하기"""
        # 모델 매핑 적용
        mapped_model = MODEL_MAPPING.get(model, model)
        
        # 🔍 웹 검색 관련 메시지 필터링 (이전 검색 결과 제거)
        filtered_messages = self._filter_messages(messages)
        
        # 스트리밍 응답 생성
        stream = self.openai_client.chat.completions.create(
            model=mapped_model,
            messages=filtered_messages,
            temperature=0.7,
            max_tokens=1000,
            stream=True
        )
        
        return stream
    
    def _filter_messages(self, messages: List[dict]) -> List[dict]:
        """🔍 메시지 필터링 공통 로직"""
        filtered_messages = []
        filter_keywords = [
            "삼일회계법인", "웹 검색:", "검색 결과:", 
            "bizbank.co.kr", "oldee.kr", "ytn.co.kr", "sedaily.com"
        ]
        
        for msg in messages:
            # system 역할의 메시지 중 특정 키워드가 포함된 것들을 필터링
            if msg.get("role") == "system" and any(keyword in msg.get("content", "") for keyword in filter_keywords):
                logger.info(f"🚫 웹 검색 관련 시스템 메시지 필터링: {msg.get('content', '')[:50]}...")
                continue
            
            # 사용자 메시지 중 웹 검색 접두사 제거
            content = msg.get("content", "")
            if msg.get("role") == "user" and content.startswith("웹 검색:"):
                content = content.replace("웹 검색:", "").strip()
                msg = {**msg, "content": content}
            
            filtered_messages.append(msg)
        
        logger.info(f"📊 메시지 필터링: {len(messages)} → {len(filtered_messages)} (제거된 메시지: {len(messages) - len(filtered_messages)}개)")
        return filtered_messages
    
    async def _save_ai_answer(self, message: Message, ai_response: dict, model: str) -> None:
        """💾 AI 답변 저장하기"""
        message.answer = ai_response["content"]
        message.status = "completed"
        message.model_used = model
        message.question_tokens = ai_response["usage"]["prompt_tokens"]
        message.answer_tokens = ai_response["usage"]["completion_tokens"]
        message.answer_time = datetime.now()
        
        await save_to_db(self.db, message)
    
    async def _update_conversation_stats(self, conversation_id: int, usage: dict) -> None:
        """📊 대화방 통계 업데이트"""
        conversation = await get_by_id(self.db, Conversation, conversation_id)
        if conversation:
            conversation.message_count += 1
            conversation.total_tokens += usage.get("total_tokens", 0)
            conversation.updated_at = datetime.now()
            await save_to_db(self.db, conversation)
    
    async def _mark_message_failed(self, message_id: int, error_message: str) -> None:
        """❌ 메시지 실패 처리"""
        message = await get_by_id(self.db, Message, message_id)
        if message:
            message.status = "failed"
            message.extra_info = error_message
            await save_to_db(self.db, message)
    
    
    async def update_conversation_title(self, conversation_id: int, title: str) -> bool:
        """✏️ 대화 제목 수정하기"""
        conversation = await get_by_id(self.db, Conversation, conversation_id)
        if conversation and not conversation.is_deleted:
            conversation.title = title
            conversation.updated_at = datetime.now()
            await save_to_db(self.db, conversation)
            return True
        return False
    
    async def delete_conversation(self, conversation_id: int) -> bool:
        """🗑️ 대화 삭제하기 (soft delete)"""
        conversation = await get_by_id(self.db, Conversation, conversation_id)
        if conversation and not conversation.is_deleted:
            conversation.is_deleted = True
            conversation.updated_at = datetime.now()
            await save_to_db(self.db, conversation)
            return True
        return False