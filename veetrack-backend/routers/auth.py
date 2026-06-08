from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import timedelta

from database import get_db
from models import User
from auth.jwt import (
    verify_password, create_access_token, create_refresh_token, 
    ACCESS_TOKEN_EXPIRE_MINUTES, verify_token
)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password) or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role_name}, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data={"sub": user.username, "role": user.role_name})
    
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh")
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    token_data = verify_token(refresh_token, "refresh")
    if token_data is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
        
    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.username == token_data.username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive or deleted")
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(
        data={"sub": user.username, "role": user.role_name}, expires_delta=access_token_expires
    )
    new_refresh_token = create_refresh_token(data={"sub": user.username, "role": user.role_name})
    
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }

@router.post("/logout")
async def logout():
    # In a fully stateless JWT system, client deletes the token.
    # To properly invalidate, we would need a Redis token blocklist.
    return {"msg": "Successfully logged out"}
