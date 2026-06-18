from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.main.database import get_db
from app.main import models, schemas

router = APIRouter(prefix="/api/marks", tags=["Evaluation Marks Engine"])

@router.post("/", response_model=schemas.MarkResponse, status_code=status.HTTP_201_CREATED)
def add_student_mark(payload: schemas.MarkCreate, db: Session = Depends(get_db)):
    """
    Submits a checked exam score matching a specific student ID and paper reference code.
    """
    student_exists = db.query(models.Student).filter(models.Student.id == payload.student_id).first()
    if not student_exists:
        raise HTTPException(status_code=404, detail="Selected student registry entry not found.")
        
    db_mark = models.EvaluationMark(
        student_id=payload.student_id,
        paper_number=payload.paper_number,
        marks=payload.marks
    )
    db.add(db_mark)
    db.commit()
    db.refresh(db_mark)
    return db_mark


@router.get("/student/{student_id}", response_model=List[schemas.MarkResponse])
def get_all_marks_for_student(student_id: int, db: Session = Depends(get_db)):
    """
    Retrieves the complete historical array of marks for a specific student.
    Your frontend splits this list between Pure and Applied based on the paper_number.
    """
    return db.query(models.EvaluationMark)\
             .filter(models.EvaluationMark.student_id == student_id)\
             .order_by(models.EvaluationMark.paper_number.asc())\
             .all()