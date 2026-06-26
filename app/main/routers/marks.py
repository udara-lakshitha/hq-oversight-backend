from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os
import shutil

from app.main.database import get_db
from app.main import models, schemas
from app.main.routers.auth import get_current_student

router = APIRouter(prefix="/api/marks", tags=["Evaluation Marks Engine"])

# File system storage paths configuration
UPLOAD_DIR = "./uploads/submissions"
PAPERS_DIR = "./uploads/question_papers"
SCHEMES_DIR = "./uploads/marking_schemes"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PAPERS_DIR, exist_ok=True)
os.makedirs(SCHEMES_DIR, exist_ok=True)


@router.post("/", response_model=schemas.MarkResponse, status_code=status.HTTP_201_CREATED)
def add_student_mark(payload: schemas.MarkCreate, db: Session = Depends(get_db)):
    """
    Submits a checked exam score matching a specific student ID and target exam.
    """
    student_exists = db.query(models.Student).filter(models.Student.id == payload.student_id).first()
    if not student_exists:
        raise HTTPException(status_code=404, detail="Selected student registry entry not found.")
        
    exam_exists = db.query(models.Exam).filter(models.Exam.id == payload.exam_id).first()
    if not exam_exists:
        raise HTTPException(status_code=404, detail="Selected exam model registry entry not found.")

    db_mark = models.EvaluationMark(
        student_id=payload.student_id,
        exam_id=payload.exam_id,
        marks=payload.marks
    )
    db.add(db_mark)
    db.commit()
    db.refresh(db_mark)
    return db_mark


@router.get("/student/{student_id}")
def get_all_marks_for_student(student_id: int, db: Session = Depends(get_db)):
    """
    Fetches all compiled scores for a given student ID, joining across 
    the Exam model to retrieve the real paper_number text string dynamically.
    """
    results = (
        db.query(models.EvaluationMark, models.Exam.paper_number)
        .join(models.Exam, models.EvaluationMark.exam_id == models.Exam.id)
        .filter(models.EvaluationMark.student_id == student_id)
        .all()
    )

    # Reconstruct dictionary so your frontend preserves .paper_number and .marks fields safely
    serialized_history = []
    for mark, paper_number in results:
        serialized_history.append({
            "id": mark.id,
            "student_id": mark.student_id,
            "paper_number": paper_number,  # "HQ 1", "HQ 2", etc.
            "marks": mark.marks,
            "created_at": mark.created_at.isoformat() if mark.created_at else None
        })
        
    return serialized_history


@router.get("/past-papers")
def get_past_papers(db: Session = Depends(get_db)):
    """
    Fetches all core exam paper archives registered in the ecosystem database.
    """
    return db.query(models.Exam).order_by(models.Exam.paper_number.asc()).all()


@router.post("/submit-paper/{exam_id}")
def upload_student_submission(
    exam_id: int, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_student: models.Student = Depends(get_current_student)
):
    """
    Receives and caches a physical student answer sheet attachment workspace on disk,
    and commits a metadata log tracking state to unlock marking schemes.
    """
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Target exam registry module not found.")

    # Format file naming systematically
    file_name = f"submission_stud_{current_student.id}_exam_{exam_id}_{file.filename}"
    destination_path = os.path.join(UPLOAD_DIR, file_name)
    
    with open(destination_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Check if a submission tracking model is already present to handle re-uploads cleanly
    existing_submission = db.query(models.ExamSubmission).filter(
        models.ExamSubmission.student_id == current_student.id,
        models.ExamSubmission.exam_id == exam_id
    ).first()

    if existing_submission:
        existing_submission.submitted_file_path = destination_path
        db.commit()
    else:
        new_submission = models.ExamSubmission(
            student_id=current_student.id,
            exam_id=exam_id,
            submitted_file_path=destination_path
        )
        db.add(new_submission)
        db.commit()
        
    return {
        "detail": "Transmission completed successfully.",
        "saved_filename": file_name,
        "absolute_storage_path": os.path.abspath(destination_path)
    }


@router.get("/stream-paper/{exam_id}")
def download_question_paper(exam_id: int, db: Session = Depends(get_db)):
    """
    Streams a physical PDF question paper resource back to the student's dashboard workspace.
    """
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam or not exam.question_file_path:
        fallback_pdf_path = "./test_question.pdf"
    else:
        fallback_pdf_path = exam.question_file_path
    
    if os.path.exists(fallback_pdf_path):
        filename_header = f"HQ_Module_{exam_id}_Questions.pdf" if not exam else f"{exam.paper_number}_Questions.pdf"
        return FileResponse(
            fallback_pdf_path, 
            media_type="application/pdf", 
            filename=filename_header
        )
    
    raise HTTPException(
        status_code=404, 
        detail="Target PDF question paper file wasn't found at the server workspace."
    )


@router.get("/stream-scheme/{exam_id}")
def download_marking_scheme(
    exam_id: int, 
    db: Session = Depends(get_db), 
    current_student: models.Student = Depends(get_current_student)
):
    """
    Streams a corresponding evaluated marking scheme resource structure down to the caller interface,
    BUT ONLY if the student has already uploaded a valid solution file asset matrix for this paper.
    """
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Requested exam resource not found.")

    # Rule Verification Check: Verify if a submission exists for this student and this exam
    submission_exists = db.query(models.ExamSubmission).filter(
        models.ExamSubmission.student_id == current_student.id,
        models.ExamSubmission.exam_id == exam_id
    ).first()

    if not submission_exists:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Access Denied: Marking schemes are reserved exclusively for students who completed submissions."
        )

    scheme_path = exam.marking_scheme_path or "./test_question.pdf"
    
    if os.path.exists(scheme_path):
        return FileResponse(
            scheme_path,
            media_type="application/pdf",
            filename=f"{exam.paper_number}_Marking_Scheme.pdf"
        )
    
    raise HTTPException(
        status_code=404, 
        detail="The target marking scheme PDF file artifact is temporarily unavailable on the server root."
    )