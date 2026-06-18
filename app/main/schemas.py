from pydantic import BaseModel, EmailStr
from typing import Optional

class StudentBase(BaseModel):
    name: str
    email: EmailStr
    phone_number: str

class StudentCreate(BaseModel):
    name: str
    email: EmailStr
    phone_number: str
    password: str

class StudentResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone_number: str
    profile_pic_path: Optional[str] = None

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_token: Optional[str] = None

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp_code: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    device_token: Optional[str] = None
    student: StudentResponse