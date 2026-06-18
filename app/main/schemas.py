from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class StudentBase(BaseModel):
    name: str
    email: EmailStr
    phone_number: str

class StudentCreate(BaseModel):
    name: str
    email: EmailStr
    phone_number: str
    password: str
    profile_pic_path: Optional[str] = None

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
    device_token: Optional[str] = None  # Optional parameter for bypass tracking

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp_code: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    device_token: Optional[str] = None
    student: StudentResponse

class MarkCreate(BaseModel):
    student_id: int
    paper_number: str
    marks: float

class MarkResponse(BaseModel):
    id: int
    student_id: int
    paper_number: str
    marks: float
    created_at: datetime

    class Config:
        from_attributes = True