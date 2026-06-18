from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import bcrypt
import random
import jwt
import secrets
from datetime import datetime, timedelta, timezone
from app.main.database import get_db
from app.main.models import Student, StudentDevice
from app.main.schemas import LoginRequest, VerifyOTPRequest, TokenResponse
from app.main.utils import send_verification_email

router = APIRouter(prefix="/auth", tags=["Authentication"])

JWT_SECRET = "HQ_OVERSIGHT_SUPER_SECRET_MATHEMATICS_KEY_2026"
JWT_ALGORITHM = "HS256"

otp_storage = {}

def generate_jwt_token(email: str) -> str:
    token_payload = {
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=1)
    }
    return jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.post("/login")
def login_step_one(payload: LoginRequest, db: Session = Depends(get_db)):
    # 1. Verify student profile registry exists
    student = db.query(Student).filter(Student.email == payload.email).first()
    if not student:
        raise HTTPException(status_code=401, detail="Invalid email or password parameters matched.")

    # 2. Authenticate cryptographic password block signatures
    password_match = bcrypt.checkpw(payload.password.encode('utf-8'), student.hashed_password.encode('utf-8'))
    if not password_match:
        raise HTTPException(status_code=401, detail="Invalid email or password parameters matched.")

    # 3. DEVICE SECURITY BYPASS ROUTING
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
                    "profile_pic_path": student.profile_pic_path
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
        raise HTTPException(status_code=400, detail="Authentication session expired or not initialized.")

    if datetime.now(timezone.utc) > session["expires_at"]:
        otp_storage.pop(payload.email, None)
        raise HTTPException(status_code=400, detail="Your verification passkey has expired.")

    if session["otp"] != payload.otp_code:
        raise HTTPException(status_code=401, detail="Incorrect security passkey verification failed.")

    student = db.query(Student).filter(Student.email == payload.email).first()
    otp_storage.pop(payload.email, None)

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