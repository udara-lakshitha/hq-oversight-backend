import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import bcrypt

from app.main.database import get_db
from app.main.models import Student
from app.main.schemas import StudentCreate, StudentResponse

router = APIRouter(prefix="/students", tags=["Students"])

BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))


@router.post("/", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def register_student(student_in: StudentCreate, db: Session = Depends(get_db)):
    # Verify email uniqueness
    existing_email = db.query(Student).filter(Student.email == student_in.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A student profile with this email address already exists."
        )

    existing_phone = db.query(Student).filter(Student.phone_number == student_in.phone_number).first()
    if existing_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A student profile with this mobile number already exists."
        )

    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed_pw_bytes = bcrypt.hashpw(student_in.password.encode('utf-8'), salt)
    hashed_password_string = hashed_pw_bytes.decode('utf-8')

    new_student = Student(
        name=student_in.name,
        email=student_in.email,
        phone_number=student_in.phone_number,
        hashed_password=hashed_password_string,
        profile_pic_path=student_in.profile_pic_path
    )
    
    db.add(new_student)
    db.commit()
    db.refresh(new_student)
    return new_student