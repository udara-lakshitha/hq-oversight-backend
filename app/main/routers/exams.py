import os
import io
from datetime import datetime, time, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.main.database import get_db
from app.main import models
from app.main.routers.auth import get_current_student
from app.utils.storage import upload_file_to_supabase, get_file_from_supabase

router = APIRouter(prefix="/api/exams", tags=["Synchronized Examination Stream"])

DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE", "False").lower() in ("true", "1", "yes")
MOCK_LIVE_MODE = os.getenv("MOCK_LIVE_MODE", "False").lower() in ("true", "1", "yes")

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
    matched_weekday = None

    for weekday in CLASS_WEEKDAYS:
        start_datetime = now.replace(hour=START_HOUR, minute=START_MINUTE, second=0, microsecond=0)
        if now.weekday() != weekday:
            days_back = (now.weekday() - weekday) % 7
            start_datetime -= timedelta(days=days_back)
            
        if start_datetime.weekday() == weekday:
            end_datetime = start_datetime + timedelta(hours=DURATION_HOURS, minutes=DURATION_MINUTES)
            if start_datetime <= now <= end_datetime:
                if now.date() == start_datetime.date():
                    is_live = True
                    matched_weekday = weekday
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

    return is_live, target_hq_num, matched_weekday


@router.get("/live-session")
def get_active_live_session(
    db: Session = Depends(get_db),
    current_student: models.Student = Depends(get_current_student),
    x_device_token: str = Header(None, alias="X-Device-Token")
):
    verify_active_device_session(current_student.id, x_device_token, db)

    is_live, target_hq_num, matched_weekday = get_biweekly_schedule_state(db)
    target_paper_code = f"HQ {target_hq_num}"

    now = datetime.now()
    seconds_remaining = 0

    if is_live:
        start_datetime = now.replace(hour=START_HOUR, minute=START_MINUTE, second=0, microsecond=0)
        if now.weekday() != matched_weekday:
            days_back = (now.weekday() - matched_weekday) % 7
            start_datetime -= timedelta(days=days_back)
            
        end_datetime = start_datetime + timedelta(hours=DURATION_HOURS, minutes=DURATION_MINUTES)
        seconds_remaining = max(0, int((end_datetime - now).total_seconds()))
    else:
        upcoming_targets = []
        for weekday in CLASS_WEEKDAYS:
            days_ahead = (weekday - now.weekday()) % 7
            if days_ahead == 0:
                past_end = now.replace(hour=START_HOUR, minute=START_MINUTE, second=0, microsecond=0) + timedelta(hours=DURATION_HOURS, minutes=DURATION_MINUTES)
                if now > past_end:
                    days_ahead = 7
            target_start = now.replace(hour=START_HOUR, minute=START_MINUTE, second=0, microsecond=0) + timedelta(days=days_ahead)
            upcoming_targets.append(target_start)
            
        next_class_start = min(upcoming_targets)
        seconds_remaining = max(0, int((next_class_start - now).total_seconds()))

    exam = db.query(models.Exam).filter(models.Exam.paper_number == target_paper_code).first()

    if is_live and not exam:
        exam = db.query(models.Exam).order_by(models.Exam.id.desc()).first()

    return {
        "is_live": is_live,
        "seconds_remaining": seconds_remaining,
        "target_hq_num": target_hq_num,
        "target_paper_code": target_paper_code,
        "exam": exam if is_live else None
    }


@router.get("/stream-paper/{exam_id}")
def stream_exam_file_pdf(
    exam_id: int,
    file_type: str = "paper",
    db: Session = Depends(get_db),
    current_student: models.Student = Depends(get_current_student),
    x_device_token: str = Header(None, alias="X-Device-Token")
):
    verify_active_device_session(current_student.id, x_device_token, db)

    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Requested exam record missing from database storage."
        )
    
    evaluation = None
    if file_type in ["scheme", "feedback"]:
        evaluation = db.query(models.EvaluationMark).filter(
            models.EvaluationMark.student_id == current_student.id,
            models.EvaluationMark.exam_id == exam_id
        ).first()

    if file_type == "scheme":
        if not evaluation:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Access Denied. Marking scheme unlocks after your script is evaluated."
            )
        file_path = exam.marking_scheme_path
        download_name = f"Exam_{exam_id}_Marking_Scheme.pdf"
        
    elif file_type == "feedback":
        if not evaluation or not evaluation.feedback_file_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="No graded feedback sheet available for your submission yet."
            )
        file_path = evaluation.feedback_file_path
        download_name = f"Exam_{exam_id}_Feedback.pdf"
        
    else:
        file_path = exam.question_file_path
        download_name = f"Exam_{exam_id}_Questions.pdf"

    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Requested asset file type path [{file_type}] trace missing from database record."
        )
        
    try:
        file_bytes = get_file_from_supabase(file_path)
        
        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename={download_name}"}
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Target binary object not found inside Supabase cloud storage bucket storage arrays."
        )


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

    file_bytes = await file.read()
    sanitized_filename = f"student_{current_student.id}_exam_{exam_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    try:
        storage_path = upload_file_to_supabase(file_bytes, sanitized_filename, folder="student_submissions")
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Supabase upload configuration failed: {str(err)}"
        )

    new_submission = models.ExamSubmission(
        student_id=current_student.id,
        exam_id=exam_id,
        submitted_file_path=storage_path,
        submitted_at=datetime.now()
    )
    db.add(new_submission)
    db.commit()
    db.refresh(new_submission)

    return {"status": "Success", "message": "Payload verified, saved, and appended onto evaluative structures cleanly."}