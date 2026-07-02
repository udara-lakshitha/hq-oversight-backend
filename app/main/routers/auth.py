import os
import random
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import bcrypt
import jwt

from app.main.database import get_db
from app.main.models import Student, StudentDevice
from app.main.schemas import LoginRequest, VerifyOTPRequest, TokenResponse, PasswordUpdatePayload
from app.main.utils import send_verification_email, send_recovery_email

router = APIRouter(prefix="/auth", tags=["Authentication"])
security_guard = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET", "FALLBACK_DEVELOPMENT_KEY_DO_NOT_USE_IN_PROD")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

otp_storage = {}

def generate_jwt_token(email: str) -> str:
    token_payload = {
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=1)
    }
    return jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def get_current_student(credentials: HTTPAuthorizationCredentials = Depends(security_guard), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token properties.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session token signature expired or corrupt.")
        
    student = db.query(Student).filter(Student.email == email).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Target student profile missing from registry.")
    return student


@router.post("/login")
def login_step_one(payload: LoginRequest, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.email == payload.email).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password parameters matched.")

    password_match = bcrypt.checkpw(payload.password.encode('utf-8'), student.hashed_password.encode('utf-8'))
    if not password_match:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password parameters matched.")

    if payload.device_token:
        known_device = db.query(StudentDevice).filter(
            StudentDevice.student_id == student.id,
            StudentDevice.device_token == payload.device_token
        ).first()
        
        if known_device:
            token = generate_jwt_token(student.email)
            return {
                "step_two_required": False,
                "access_token": token,
                "token_type": "bearer",
                "device_token": known_device.device_token, 
                "student": {
                    "id": student.id,
                    "name": student.name,
                    "email": student.email,
                    "phone_number": student.phone_number,
                    "profile_pic_path": student.profile_pic_path,
                    "role": student.role,
                    "is_temporary_password": student.is_temporary_password
                }
            }

    generated_otp = str(random.randint(100000, 999999))
    otp_storage[student.email] = {
        "otp": generated_otp,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5)
    }

    send_verification_email(
        student_name=student.name,
        target_email=student.email,
        otp_code=generated_otp
    )

    return {
        "step_two_required": True,
        "message": "Verification passcode dispatched to registered device channel.",
        "email": student.email
    }


@router.post("/verify-otp", response_model=TokenResponse)
def login_step_two(payload: VerifyOTPRequest, db: Session = Depends(get_db)):
    session = otp_storage.get(payload.email)
    if not session:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authentication session expired or not initialized.")

    if datetime.now(timezone.utc) > session["expires_at"]:
        otp_storage.pop(payload.email, None)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your verification passkey has expired.")

    if session["otp"] != payload.otp_code:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect security passkey verification failed.")

    student = db.query(Student).filter(Student.email == payload.email).first()
    otp_storage.pop(payload.email, None)

    db.query(StudentDevice).filter(StudentDevice.student_id == student.id).delete()

    new_device_token = secrets.token_hex(32)
    db_device = StudentDevice(student_id=student.id, device_token=new_device_token)
    db.add(db_device)
    db.commit()

    token = generate_jwt_token(student.email)

    return {
        "access_token": token,
        "token_type": "bearer",
        "device_token": new_device_token,  
        "student": student
    }

@router.post("/forgot-password")
def forgot_password_recovery(email: str = Form(...), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.email == email).first()
    if not student:
        return {"status": "processed", "message": "If the account matches, an email will be sent."}
    
    temp_password = secrets.token_urlsafe(6) 
    
    student.hashed_password = bcrypt.hashpw(temp_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    student.is_temporary_password = True
    db.commit()

    send_recovery_email(
        student_name=student.name,
        target_email=student.email,
        temporary_password=temp_password
    )
    
    return {"status": "success", "message": "A temporary password has been sent to your email."}

@router.post("/update-forced-password")
def update_forced_password(payload: PasswordUpdatePayload, db: Session = Depends(get_db)):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")
        
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")
        
    student = db.query(Student).filter(Student.email == payload.email).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student account not found.")
        
    student.hashed_password = bcrypt.hashpw(payload.new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    student.is_temporary_password = False
    db.commit()
    
    return {"status": "success", "message": "Password updated successfully. You can now log in."}

@router.post("/logout")
def logout_user(current_student: Student = Depends(get_current_student)):
    # [Todo] - should be expand this based on cookies in future
    print("🔒 Backend compilation audit: Active user session securely dropped.")
    return {"status": "success", "message": "Portal session terminated successfully."}