from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime
import os
import shutil

from app.main.database import get_db
from app.main import models, schemas
from app.main.routers.auth import get_current_student

router = APIRouter(prefix="/api/exams", tags=["Synchronized Examination Stream"])

DEVELOPMENT_MODE = True  # Toggle True to bypass time window constraints during testing

UPLOAD_DIR = "./uploads/submissions"
PAPERS_DIR = "./uploads/question_papers"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PAPERS_DIR, exist_ok=True)


@router.get("/live-session", response_model=schemas.ExamResponse)
def get_active_live_session(db: Session = Depends(get_db)):
    """
    Checks if a synchronized exam session stream is open and valid based on timeline parameters.
    """
    now = datetime.now()
    
    active_exam = db.query(models.Exam).order_by(models.Exam.created_at.desc()).first()
    if not active_exam:
        raise HTTPException(
            status_code=404, 
            detail="System locked. No examination streams have been registered yet."
        )

    if DEVELOPMENT_MODE:
        return active_exam

    is_friday = (now.weekday() == 4)
    is_in_time_window = (21 <= now.hour <= 23)

    if not (is_friday and is_in_time_window):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"🔒 System locked. Next synchronized live stream open on Friday (9:00 PM - 12:00 AM strictly). Target: {active_exam.paper_number}"
        )

    return active_exam


@router.post("/submit-live/{exam_id}")
def upload_live_answer_sheet(
    exam_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_student: models.Student = Depends(get_current_student)
):
    """
    Handles live examination file updates into the secure storage workspace disk.
    """
    if not DEVELOPMENT_MODE:
        now = datetime.now()
        if not (now.weekday() == 4 and 21 <= now.hour <= 23):
            raise HTTPException(status_code=403, detail="The examination session submission window has closed.")

    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Target examination framework metadata not found.")

    file_name = f"live_submission_student_{current_student.id}_exam_{exam_id}_{file.filename}"
    destination_path = os.path.join(UPLOAD_DIR, file_name)

    with open(destination_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    submission = db.query(models.ExamSubmission).filter(
        models.ExamSubmission.student_id == current_student.id,
        models.ExamSubmission.exam_id == exam_id
    ).first()

    if submission:
        submission.submitted_file_path = destination_path
        db.commit()
    else:
        submission = models.ExamSubmission(
            student_id=current_student.id,
            exam_id=exam_id,
            submitted_file_path=destination_path
        )
        db.add(submission)
        db.commit()

    return {
        "status": "success",
        "detail": "Live tracking submission received and cached cleanly.",
        "filename": file_name
    }


@router.get("/stream-paper/{exam_id}")
def download_question_paper(exam_id: int, db: Session = Depends(get_db)):
    """
    Streams a physical PDF question paper resource back to the client interface workspace.
    Dynamically normalizes filenames to match variations like HQ_07_Questions.pdf or hq7_questions.pdf.
    """
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam or not exam.question_file_path:
        raise HTTPException(status_code=404, detail="Target examination question profile path database reference not found.")
    
    db_filename = os.path.basename(exam.question_file_path)
    
    def normalize_string(name: str) -> str:
        return name.lower().replace(" ", "").replace("_", "").replace("-", "")

    target_normalized = normalize_string(db_filename)

    if os.path.exists(PAPERS_DIR):
        for actual_file in os.listdir(PAPERS_DIR):
            if normalize_string(actual_file) == target_normalized:
                matched_absolute_path = os.path.join(PAPERS_DIR, actual_file)
                return FileResponse(
                    matched_absolute_path, 
                    media_type="application/pdf", 
                    filename=actual_file
                )
                
    raise HTTPException(
        status_code=404, 
        detail=f"Fuzzy Match Failed: No files inside '{PAPERS_DIR}' matched the signature for '{db_filename}'."
    )