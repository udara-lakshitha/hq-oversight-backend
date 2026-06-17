from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import bcrypt
import random
import jwt
from datetime import datetime, timedelta, timezone
from app.main.database import get_db
from app.main.models import Student
from app.main.schemas import LoginRequest, VerifyOTPRequest, TokenResponse
from app.main.utils import send_verification_email

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Secret key to sign our system login tokens locally
JWT_SECRET = "HQ_OVERSIGHT_SUPER_SECRET_MATHEMATICS_KEY_2026"
JWT_ALGORITHM = "HS256"

# Temporary storage dictionary to hold active OTP codes in memory
otp_storage = {}

@router.post("/login")
def login_step_one(payload: LoginRequest, db: Session = Depends(get_db)):
    # 1. Look up student by email
    student = db.query(Student).filter(Student.email == payload.email).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password parameters matched."
        )

    # 2. Verify password signature matches
    password_match = bcrypt.checkpw(
        payload.password.encode('utf-8'), 
        student.hashed_password.encode('utf-8')
    )
    if not password_match:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password parameters matched."
        )

    # 3. Generate a 6-digit code
    generated_otp = str(random.randint(100000, 999999))
    expiration_time = datetime.now(timezone.utc) + timedelta(minutes=5)

    # 4. Save to temporary storage
    otp_storage[student.email] = {
        "otp": generated_otp,
        "expires_at": expiration_time
    }

    # 5. Dispatch the email communication trigger
    send_verification_email(
        student_name=student.name,
        target_email=student.email,
        otp_code=generated_otp
    )

    return {"message": "Verification passcode dispatched successfully.", "email": student.email}


@router.post("/verify-otp", response_model=TokenResponse)
def login_step_two(payload: VerifyOTPRequest, db: Session = Depends(get_db)):
    session = otp_storage.get(payload.email)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication session expired or not initialized."
        )

    if datetime.now(timezone.utc) > session["expires_at"]:
        otp_storage.pop(payload.email, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your verification passkey has expired. Please log in again."
        )

    if session["otp"] != payload.otp_code:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect security passkey verification failed."
        )

    student = db.query(Student).filter(Student.email == payload.email).first()
    otp_storage.pop(payload.email, None) # Clear OTP once verified

    # Generate active 1-day login session key
    token_payload = {
        "sub": student.email,
        "exp": datetime.now(timezone.utc) + timedelta(days=1)
    }
    encoded_jwt = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return {
        "access_token": encoded_jwt,
        "token_type": "bearer",
        "student": student
    }