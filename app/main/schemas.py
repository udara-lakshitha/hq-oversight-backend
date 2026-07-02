from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class StudentBase(BaseModel):
    name: str
    email: EmailStr
    phone_number: str


class StudentCreate(StudentBase):
    password: str
    profile_pic_path: Optional[str] = None


class StudentResponse(StudentBase):
    id: int
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


class ExamCreate(BaseModel):
    paper_number: str
    title: str
    paper_type: str
    question_file_path: str
    marking_scheme_path: Optional[str] = None


class ExamResponse(BaseModel):
    id: int
    paper_number: str
    title: str
    paper_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class MarkCreate(BaseModel):
    student_id: int
    exam_id: int
    marks: float


class MarkResponse(BaseModel):
    id: int
    student_id: int
    exam_id: int
    marks: float
    created_at: datetime

    class Config:
        from_attributes = True

class PasswordUpdatePayload(BaseModel):
    email: str
    new_password: str
    confirm_password: str