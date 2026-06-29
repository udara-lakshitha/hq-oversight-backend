import os
import shutil
from datetime import datetime, time, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Header
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.main.database import get_db
from app.main import models, schemas
from app.main.routers.auth import get_current_student

router = APIRouter(prefix="/api/exams", tags=["Synchronized Examination Stream"])

DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE", "False").lower() in ("true", "1", "yes")
MOCK_LIVE_MODE = os.getenv("MOCK_LIVE_MODE", "False").lower() in ("true", "1", "yes")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads/submissions")
PAPERS_DIR = os.getenv("PAPERS_DIR", "./uploads/question_papers")

raw_weekdays = os.getenv("CLASS_WEEKDAYS", "1,4")
CLASS_WEEKDAYS = [int(d.strip()) for d in raw_weekdays.split(",") if d.strip()]
START_HOUR = int(os.getenv("START_HOUR", "21"))
START_MINUTE = int(os.getenv("START_MINUTE", "0"))
DURATION_HOURS = int(os.getenv("DURATION_HOURS", "3"))
DURATION_MINUTES = int(os.getenv("DURATION_MINUTES", "10"))


def verify_active_device_session(student_id: int, device_token: str, db: Session):
    if not device_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Security Verification Failed: Device authentication signature header missing."
        )
    
    active_device = db.query(models.StudentDevice).filter(
        models.StudentDevice.student_id == student_id,
        models.StudentDevice.device_token == device_token
    ).first()
    
    if not active_device:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Session Terminated: Account logged in from alternative device location."
        )


def get_biweekly_schedule_state(db: Session):
    now = datetime.now()
    is_live = False

    for weekday in CLASS_WEEKDAYS:
        start_datetime = now.replace(hour=START_HOUR, minute=START_MINUTE, second=0, microsecond=0)
        if now.weekday() != weekday:
            start_datetime -= timedelta(days=1)
            
        if start_datetime.weekday() == weekday:
            end_datetime = start_datetime + timedelta(hours=DURATION_HOURS, minutes=DURATION_MINUTES)
            if start_datetime <= now <= end_datetime:
                is_live = True
                break

    latest_exam = db.query(models.Exam).order_by(models.Exam.id.desc()).first()
    
    if latest_exam and latest_exam.paper_number:
        try:
            extracted_digits = "".join(filter(str.isdigit, latest_exam.paper_number))
            max_num = int(extracted_digits) if extracted_digits else 0
        except ValueError:
            max_num = 0
    else:
        max_num = 0

    if is_live:
        target_hq_num = max_num if max_num > 0 else 1
    else:
        target_hq_num = max_num + 1

    return is_live, target_hq_num


@router.get("/live-session", response_model=schemas.ExamResponse)
def get_active_live_session(
    db: Session = Depends(get_db),
    current_student: models.Student = Depends(get_current_student),
    x_device_token: str = Header(None, alias="X-Device-Token")
):
    verify_active_device_session(current_student.id, x_device_token, db)

    if MOCK_LIVE_MODE:
        exam = db.query(models.Exam).order_by(models.Exam.id.desc()).first()
        if not exam:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Dynamic Live Override active, but your database Exam table is completely empty."
            )
        return exam

    is_live, target_hq_num = get_biweekly_schedule_state(db)
    target_paper_code = f"HQ {target_hq_num}"

    if not is_live and not DEVELOPMENT_MODE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"System locked. {target_paper_code} is scheduled for the upcoming window."
        )

    exam = db.query(models.Exam).filter(models.Exam.paper_number == target_paper_code).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Active slot open, but question asset registry profile is blank."
        )
        
    return exam


@router.get("/stream-paper/{exam_id}")
def stream_question_paper_pdf(
    exam_id: int,
    db: Session = Depends(get_db),
    current_student: models.Student = Depends(get_current_student),
    x_device_token: str = Header(None, alias="X-Device-Token")
):
    verify_active_device_session(current_student.id, x_device_token, db)

    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam or not exam.question_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Requested file record trace missing from asset storage."
        )
    
    absolute_target_path = os.path.abspath(exam.question_file_path)
    if not os.path.exists(absolute_target_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Physical PDF binary payload not present on disk array storage units."
        )
        
    return FileResponse(absolute_target_path, media_type="application/pdf", filename=f"Exam_{exam_id}_Questions.pdf")


@router.post("/submit-live/{exam_id}")
async def receive_student_answer_payload(
    exam_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_student: models.Student = Depends(get_current_student),
    x_device_token: str = Header(None, alias="X-Device-Token")
):
    verify_active_device_session(current_student.id, x_device_token, db)

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Transmission rejected: Document matrix payloads must be strictly in PDF formatting profiles."
        )

    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    sanitized_filename = f"student_{current_student.id}_exam_{exam_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    destination_file_path = os.path.join(UPLOAD_DIR, sanitized_filename)

    try:
        with open(destination_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Disk writer configuration failed: {str(err)}"
        )

    new_submission = models.ExamSubmission(
        student_id=current_student.id,
        exam_id=exam_id,
        submitted_file_path=destination_file_path,
        submitted_at=datetime.now()
    )
    db.add(new_submission)
    db.commit()
    db.refresh(new_submission)

    return {"status": "Success", "message": "Payload verified, saved, and appended onto evaluative structures cleanly."}