from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from app.main.database import get_db
from app.main import models, schemas
from app.main.routers.auth import get_current_student

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
def get_all_marks_for_student(
    student_id: int, 
    db: Session = Depends(get_db),
    current_student: models.Student = Depends(get_current_student)
):
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
def get_past_papers(
    db: Session = Depends(get_db),
    current_student: models.Student = Depends(get_current_student)
):
    from app.main.routers.exams import get_biweekly_schedule_state
    is_live, current_hq_num = get_biweekly_schedule_state(db)
    
    max_archived_hq = current_hq_num - 1
    
    all_exams = db.query(models.Exam).all()
    past_exams = []
    
    for exam in all_exams:
        try:
            num = int(exam.paper_number.replace("HQ", "").strip())
            if num <= max_archived_hq:
                past_exams.append(exam)
        except ValueError:
            past_exams.append(exam)
            
    return sorted(past_exams, key=lambda x: x.paper_number)


@router.get("/stream-scheme/{exam_id}")
def download_marking_scheme(
    exam_id: int, 
    db: Session = Depends(get_db),
    current_student: models.Student = Depends(get_current_student)
):
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam or not exam.marking_scheme_path:
        raise HTTPException(status_code=404, detail="Target marking scheme record or file path not found.")
    
    graded_mark_exists = db.query(models.EvaluationMark).filter(
        models.EvaluationMark.student_id == current_student.id,
        models.EvaluationMark.exam_id == exam_id
    ).first()

    if not graded_mark_exists:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="🔒 Access Denied. The marking scheme for this paper remains locked because your submission has not been evaluated yet."
        )
    
    db_filename = os.path.basename(exam.marking_scheme_path)
    
    def normalize_string(name: str) -> str:
        return name.lower().replace(" ", "").replace("_", "").replace("-", "")

    target_normalized = normalize_string(db_filename)
    schemes_dir = "./uploads/question_papers"

    if os.path.exists(schemes_dir):
        for actual_file in os.listdir(schemes_dir):
            if normalize_string(actual_file) == target_normalized:
                return FileResponse(
                    os.path.join(schemes_dir, actual_file),
                    media_type="application/pdf",
                    filename=actual_file
                )
    
    raise HTTPException(status_code=404, detail="Physical marking scheme PDF asset wasn't found on server storage.")