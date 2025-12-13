"""
Authentication router.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from admin.auth import create_access_token, hash_password, verify_password
from database.repositories.admin_user import AdminUserRepository
from config.settings import settings


router = APIRouter()
admin_repo = AdminUserRepository()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: dict


class CreateAdminRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Авторизация администратора."""
    
    admin = await admin_repo.get_by_email(request.email)
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    if not verify_password(request.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    
    # Обновляем время входа
    await admin_repo.update_last_login(admin.id)
    
    # Создаём токен
    token = create_access_token({"sub": admin.id})
    
    return LoginResponse(
        access_token=token,
        admin={
            "id": admin.id,
            "email": admin.email,
            "name": admin.name,
            "role": admin.role,
        }
    )


@router.post("/setup")
async def setup_admin():
    """
    Первоначальная настройка — создание админа по умолчанию.
    Работает только если нет ни одного админа.
    """
    existing = await admin_repo.get_all()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin already exists. Use login instead.",
        )
    
    # Создаём дефолтного админа
    password_hash = hash_password(settings.ADMIN_DEFAULT_PASSWORD)
    
    admin = await admin_repo.create(
        email=settings.ADMIN_DEFAULT_EMAIL,
        password_hash=password_hash,
        name="Administrator",
        role="superadmin",
    )
    
    return {
        "message": "Admin created successfully",
        "email": admin.email,
        "note": "Please change the default password immediately!",
    }
