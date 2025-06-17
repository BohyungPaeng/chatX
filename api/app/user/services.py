# 👤 사용자 관련 서비스 - 사용자 정보를 관리합니다

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, Tuple

from ..models import User
from ..core.database import save_to_db, get_by_field, get_by_id


class UserService:
    """사용자 관련 비즈니스 로직을 처리하는 서비스"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_or_create_user_by_email(self, email: str, name: str = None) -> Tuple[User, bool]:
        """
        📧 이메일로 사용자 찾기 또는 새로 만들기 (SSO 환경용)
        
        Args:
            email: 사용자 이메일
            name: 사용자 이름 (선택사항)
            
        Returns:
            Tuple[User, bool]: (사용자 객체, 새로 생성됨 여부)
        """
        # 기존 사용자 찾기
        user = await get_by_field(self.db, User, "email", email)
        
        if user:
            # 마지막 로그인 시간 업데이트
            await self.update_last_login(user.id)
            return user, False  # 기존 사용자
        
        # 새 사용자 생성
        user_data = {
            "email": email,
            "name": name or email.split('@')[0],  # 이름이 없으면 이메일 앞부분 사용
            "is_active": True
        }
        
        user = User(**user_data)
        user = await save_to_db(self.db, user)
        return user, True  # 새로 생성된 사용자
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """📧 이메일로 사용자 찾기"""
        return await get_by_field(self.db, User, "email", email)
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """🆔 ID로 사용자 찾기"""
        return await get_by_id(self.db, User, user_id)
    
    async def update_last_login(self, user_id: int) -> None:
        """🕐 마지막 로그인 시간 업데이트"""
        user = await get_by_id(self.db, User, user_id)
        if user:
            user.last_login = func.now()
            await save_to_db(self.db, user)
    
    
    async def deactivate_user(self, user_id: int) -> bool:
        """❌ 사용자 비활성화"""
        user = await get_by_id(self.db, User, user_id)
        if user:
            user.is_active = False
            await save_to_db(self.db, user)
            return True
        return False