from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from app.main.database import get_db
from app.main import models, schemas

router = APIRouter(prefix="/api/marks", tags=["Evaluation Marks Engine"])

@router.post("/", response_model=schemas.MarkResponse, status_code=status.HTTP_201_CREATED)
def add_student_mark(payload: schemas.MarkCreate, db: Session = Depends(get_db)):
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
    results = (
        db.query(models.EvaluationMark, models.Exam.paper_number)
        .join(models.Exam, models.EvaluationMark.exam_id == models.Exam.id)
        .filter(models.EvaluationMark.student_id == student_id)
        .all()
    )

    serialized_history = []
    for mark, paper_number in results:
        serialized_history.append({
            "id": mark.id,
            "student_id": mark.student_id,
            "exam_id": mark.exam_id,
            "paper_number": paper_number,
            "marks": mark.marks,
            "created_at": mark.created_at.isoformat() if mark.created_at else None
        })
    return serialized_history


@router.get("/past-papers")
def get_past_papers(db: Session = Depends(get_db)):
    return db.query(models.Exam).order_by(models.Exam.paper_number.asc()).all()


@router.get("/stream-scheme/{exam_id}")
def download_marking_scheme(exam_id: int, db: Session = Depends(get_db)):
    """
    Streams a corresponding evaluated marking scheme resource file.
    """
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam or not exam.marking_scheme_path:
        raise HTTPException(status_code=404, detail="Target marking scheme record or file path not found.")
    
    if os.path.exists(exam.marking_scheme_path):
        return FileResponse(
            exam.marking_scheme_path,
            media_type="application/pdf",
            filename=f"HQ_Module_{exam_id}_Scheme.pdf"
        )
    
    raise HTTPException(status_code=404, detail="Physical marking scheme PDF asset wasn't found on server storage.")