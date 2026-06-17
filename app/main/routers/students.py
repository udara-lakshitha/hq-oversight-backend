from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import bcrypt
from app.main.database import get_db
from app.main.models import Student
from app.main.schemas import StudentCreate, StudentResponse

router = APIRouter(prefix="/students", tags=["Students"])

@router.post("/", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def register_student(student_in: StudentCreate, db: Session = Depends(get_db)):
    # 1. Check if the email address is already registered
    existing_student = db.query(Student).filter(Student.email == student_in.email).first()
    if existing_student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A student profile with this email address already exists."
        )

    # 2. Generate a secure salt and hash the password using native bcrypt
    salt = bcrypt.gensalt(rounds=12)
    hashed_pw_bytes = bcrypt.hashpw(student_in.password.encode('utf-8'), salt)
    hashed_password_string = hashed_pw_bytes.decode('utf-8')

    # 3. Save the validated profile record to SQLite
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