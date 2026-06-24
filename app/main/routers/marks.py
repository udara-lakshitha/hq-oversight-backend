from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os
import calendar
from datetime import datetime
from app.main.database import get_db
from app.main import models, schemas
from app.main.routers.auth import get_current_student

router = APIRouter(prefix="/api/marks", tags=["Evaluation Marks Engine"])

UPLOAD_DIR = "D:/projects/hq-oversight-backend/storage_vault"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def verify_active_exam_window(paper_type: str) -> bool:
    now = datetime.now()
    current_day = calendar.day_name[now.weekday()]
    current_time = now.time()

    start_gate = datetime.strptime("21:00:00", "%H:%M:%S").time()
    end_gate = datetime.strptime("23:59:59", "%H:%M:%S").time()

    if paper_type == "Pure Maths" and current_day == "Tuesday":
        return start_gate <= current_time <= end_gate
    if paper_type == "Applied Maths" and current_day == "Friday":
        return start_gate <= current_time <= end_gate
        
    return False


def has_exam_concluded(paper_type: str) -> bool:
    now = datetime.now()
    current_day = calendar.day_name[now.weekday()]
    current_time = now.time()
    
    if paper_type == "Pure Maths":
        if current_day in ["Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            return True
        if current_day == "Tuesday" and current_time > datetime.strptime("23:59:59", "%H:%M:%S").time():
            return True
    if paper_type == "Applied Maths":
        if current_day in ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday"]:
            return True
        if current_day == "Friday" and current_time > datetime.strptime("23:59:59", "%H:%M:%S").time():
            return True
    return False


@router.get("/active-paper", response_model=schemas.ExamResponse)
def get_currently_active_paper(db: Session = Depends(get_db), current_student: models.Student = Depends(get_current_student)):
    exams = db.query(models.Exam).all()
    for exam in exams:
        if verify_active_exam_window(exam.paper_type):
            return exam
            
    raise HTTPException(
        status_code=403, 
        detail="No examination parameters are scheduled within an active window at this time."
    )


@router.get("/stream-paper/{exam_id}")
def stream_exam_question_file(exam_id: int, db: Session = Depends(get_db), current_student: models.Student = Depends(get_current_student)):
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Requested paper reference code not found.")

    if not (verify_active_exam_window(exam.paper_type) or has_exam_concluded(exam.paper_type)):
        raise HTTPException(status_code=403, detail="Access denied. This examination block is securely locked.")

    if not os.path.exists(exam.question_file_path):
        raise HTTPException(status_code=404, detail="Physical file missing from storage vault.")

    return FileResponse(exam.question_file_path, media_type="application/pdf")


@router.post("/submit-paper/{exam_id}")
async def upload_student_answer_sheet(exam_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), current_student: models.Student = Depends(get_current_student)):
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Target examination mapping not found.")

    if not verify_active_exam_window(exam.paper_type):
        raise HTTPException(status_code=403, detail="Upload window closed. The 3-hour limit has expired.")

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF structures are permitted.")

    existing_sub = db.query(models.ExamSubmission).filter(
        models.ExamSubmission.student_id == current_student.id,
        models.ExamSubmission.exam_id == exam.id
    ).first()
    if existing_sub:
        raise HTTPException(status_code=400, detail="You have already submitted an execution trace for this paper.")

    file_extension = os.path.splitext(file.filename)[1]
    safe_filename = f"sub_{exam.paper_number}_{current_student.id}_{int(datetime.now().timestamp())}{file_extension}"
    target_destination = os.path.join(UPLOAD_DIR, safe_filename)

    with open(target_destination, "wb") as buffer:
        buffer.write(await file.read())

    new_submission = models.ExamSubmission(
        student_id=current_student.id,
        exam_id=exam.id,
        submitted_file_path=target_destination
    )
    db.add(new_submission)
    db.commit()

    return {"message": "Answer matrix uploaded successfully."}


@router.get("/stream-scheme/{exam_id}")
def stream_marking_scheme_file(exam_id: int, db: Session = Depends(get_db), current_student: models.Student = Depends(get_current_student)):
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Requested parameters not found.")

    if not has_exam_concluded(exam.paper_type):
        raise HTTPException(status_code=403, detail="Marking scheme locked until the exam window completely terminates.")

    has_submitted = db.query(models.ExamSubmission).filter(
        models.ExamSubmission.student_id == current_student.id,
        models.ExamSubmission.exam_id == exam.id
    ).first()

    if not has_submitted:
        raise HTTPException(
            status_code=403, 
            detail="Access Denied: Marking schemes are reserved exclusively for students who submitted answers during the active window."
        )

    if not exam.marking_scheme_path or not os.path.exists(exam.marking_scheme_path):
        raise HTTPException(status_code=404, detail="Marking scheme file not found on system disk.")

    return FileResponse(exam.marking_scheme_path, media_type="application/pdf")


@router.get("/past-papers", response_model=List[schemas.ExamResponse])
def get_concluded_past_papers(db: Session = Depends(get_db), current_student: models.Student = Depends(get_current_student)):
    all_exams = db.query(models.Exam).all()
    concluded_exams = [exam for exam in all_exams if has_exam_concluded(exam.paper_type)]
    return concluded_exams


@router.post("/", response_model=schemas.MarkResponse, status_code=status.HTTP_201_CREATED)
def add_student_mark(payload: schemas.MarkCreate, db: Session = Depends(get_db)):
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
    return db.query(models.EvaluationMark).filter(models.EvaluationMark.student_id == student_id)\
            .order_by(models.EvaluationMark.paper_number.asc())\
            .all()