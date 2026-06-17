from pydantic import BaseModel, EmailStr
from typing import Optional

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