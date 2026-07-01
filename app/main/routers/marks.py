import os
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.main.database import get_db
from app.main import models, schemas
from app.main.routers.auth import get_current_student
from app.main.routers.exams import get_biweekly_schedule_state

router = APIRouter(prefix="/api/marks", tags=["Evaluation Marks Engine"])

QUESTION_DIR = "./uploads/question_papers"
SCHEME_DIR = "./uploads/marking_schemes"
SUBMISSIONS_DIR = "./uploads/submissions"
FEEDBACK_DIR = "./uploads/feedbacks"

for path in [QUESTION_DIR, SCHEME_DIR, SUBMISSIONS_DIR, FEEDBACK_DIR]:
    os.makedirs(path, exist_ok=True)

@router.get("/student/{student_id}")
def get_student_marks_history(student_id: int, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found.")

    records = db.query(
        models.EvaluationMark.marks,
        models.EvaluationMark.feedback_file_path,
        models.EvaluationMark.created_at,
        models.Exam.paper_number,
        models.Exam.title.label("exam_title")
    ).join(
        models.Exam, models.EvaluationMark.exam_id == models.Exam.id
    ).filter(
        models.EvaluationMark.student_id == student_id
    ).order_by(
        models.EvaluationMark.created_at.asc()
    ).all()

    history_list = []
    for r in records:
        filename = os.path.basename(r.feedback_file_path) if r.feedback_file_path else None
        
        history_list.append({
            "paper_number": r.paper_number,
            "title": r.exam_title,
            "marks": r.marks,
            "filename": filename,
            "date": r.created_at.strftime("%Y-%m-%d")
        })

    return history_list


@router.get("/past-papers")
def get_past_papers(
    db: Session = Depends(get_db),
    current_student: models.Student = Depends(get_current_student)
):
    is_live, current_hq_num, matched_weekday = get_biweekly_schedule_state(db)
    
    all_exams = db.query(models.Exam).all()
    past_exams = []
    
    for exam in all_exams:
        try:
            num = int(exam.paper_number.upper().replace("HQ", "").strip())
            
            if is_live and num >= current_hq_num:
                continue
            
            if num < current_hq_num:
                past_exams.append(exam)
                
        except ValueError:
            if not is_live:
                past_exams.append(exam)
            
    sorted_exams = sorted(past_exams, key=lambda x: x.id, reverse=True)
    
    response_payload = []
    for exam in sorted_exams:
        scheme_exists = os.path.exists(exam.marking_scheme_path) if exam.marking_scheme_path else False
        feedback_filename = f"feedback_stu_{current_student.id}.pdf"
        feedback_exists = os.path.exists(os.path.join("./uploads/feedbacks", feedback_filename))
        
        matching_mark = db.query(models.EvaluationMark).filter(
            models.EvaluationMark.student_id == current_student.id,
            models.EvaluationMark.exam_id == exam.id
        ).first()

        response_payload.append({
            "id": exam.id,
            "paper_number": exam.paper_number,
            "title": exam.title,
            "paper_type": exam.paper_type if exam.paper_type else "Pure Maths",
            "scheme_available": scheme_exists,
            "feedback_available": feedback_exists,
            "marks": matching_mark.marks if matching_mark else None
        })
        
    return response_payload


@router.post("/admin/upload-exam")
async def admin_upload_new_exam(
    paper_number: str = Form(...),
    title: str = Form(...),
    paper_type: str = Form(...),
    question_file: UploadFile = File(None),         
    marking_scheme_file: UploadFile = File(None),   
    db: Session = Depends(get_db)
):
    prefix = paper_number.lower().replace(" ", "")
    exam = db.query(models.Exam).filter(models.Exam.paper_number == paper_number).first()
    
    if not exam:
        exam = models.Exam(
            paper_number=paper_number,
            title=title,
            paper_type=paper_type,
            question_file_path="",  
            marking_scheme_path="", 
            created_at=datetime.now()
        )
        db.add(exam)
        db.flush()  

    if question_file and question_file.filename:
        q_filename = f"{prefix}_question_{question_file.filename}"
        q_path = os.path.join(QUESTION_DIR, q_filename)
        with open(q_path, "wb") as f:
            shutil.copyfileobj(question_file.file, f)
        exam.question_file_path = q_path

    if marking_scheme_file and marking_scheme_file.filename:
        m_filename = f"{prefix}_scheme_{marking_scheme_file.filename}"
        m_path = os.path.join(SCHEME_DIR, m_filename)
        with open(m_path, "wb") as f:
            shutil.copyfileobj(marking_scheme_file.file, f)
        exam.marking_scheme_path = m_path

    exam.title = title
    exam.paper_type = paper_type

    db.commit()
    return {"message": f"Successfully updated and processed assets for {paper_number}."}

@router.get("/admin/pending-submissions")
def admin_get_pending_submissions(db: Session = Depends(get_db)):
    pending_list = []
    if not os.path.exists(SUBMISSIONS_DIR):
        return []

    for filename in os.listdir(SUBMISSIONS_DIR):
        if filename.startswith("student_") and filename.endswith(".pdf"):
            try:
                clean_name = filename.replace(".pdf", "")
                parts = clean_name.split("_")
                
                student_id = int(parts[1])
                exam_id = int(parts[3])
                
                student = db.query(models.Student).filter(models.Student.id == student_id).first()
                exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
                
                if student and exam:
                    already_marked = db.query(models.EvaluationMark).filter(
                        models.EvaluationMark.student_id == student_id,
                        models.EvaluationMark.exam_id == exam_id
                    ).first()

                    if not already_marked:
                        pending_list.append({
                            "submission_id": f"{student_id}_{exam_id}",
                            "student_id": student_id,
                            "student_name": student.name,
                            "exam_id": exam_id,
                            "paper_number": exam.paper_number,
                            "filename": filename
                        })
            except (ValueError, IndexError):
                continue
                
    return pending_list

@router.get("/admin/download-submission/{filename}")
def admin_download_student_submission(filename: str):
    file_path = os.path.join(SUBMISSIONS_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Requested file path does not exist on disk.")
        
    return FileResponse(
        path=file_path, 
        media_type='application/pdf', 
        filename=filename
    )


@router.post("/admin/submit-evaluation")
async def admin_submit_evaluation(
    student_id: int = Form(...),
    exam_id: int = Form(...),
    marks: float = Form(...),
    feedback_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    os.makedirs(FEEDBACK_DIR, exist_ok=True)
    
    feedback_filename = f"feedback_stu_{student_id}_exam_{exam_id}.pdf"
    feedback_path = os.path.join(FEEDBACK_DIR, feedback_filename)
    
    with open(feedback_path, "wb") as buffer:
        buffer.write(await feedback_file.read())
        
    evaluation = db.query(models.EvaluationMark).filter(
        models.EvaluationMark.student_id == student_id,
        models.EvaluationMark.exam_id == exam_id
    ).first()
    
    if evaluation:
        evaluation.marks = marks
        evaluation.feedback_file_path = feedback_path
    else:
        new_mark = models.EvaluationMark(
            student_id=student_id,
            exam_id=exam_id,
            marks=marks,
            feedback_file_path=feedback_path
        )
        db.add(new_mark)
        
    db.commit()
    return {"status": "success", "message": "Evaluation record stored successfully."}


@router.get("/admin/gradebook")
def admin_get_gradebook_matrix(db: Session = Depends(get_db)):
    results = db.query(
        models.EvaluationMark.marks,
        models.EvaluationMark.created_at,
        models.Student.name.label("student_name"),
        models.Exam.paper_number,
        models.Exam.title.label("paper_title")
    ).join(models.Student, models.Student.id == models.EvaluationMark.student_id)\
     .join(models.Exam, models.Exam.id == models.EvaluationMark.exam_id)\
     .order_by(models.EvaluationMark.created_at.desc()).all()
     
    return [
        {
            "student_name": r.student_name,
            "paper_number": r.paper_number,
            "paper_title": r.paper_title,
            "marks": r.marks,
            "graded_at": r.created_at.strftime("%Y-%m-%d %H:%M")
        } for r in results
    ]

@router.get("/admin/download-submission/{filename}")
def admin_download_student_submission(filename: str):
    file_path = os.path.join(SUBMISSIONS_DIR, filename)
    
    if not os.path.abspath(file_path).startswith(os.path.abspath(SUBMISSIONS_DIR)):
        raise HTTPException(status_code=400, detail="Unauthorized system tree navigation.")
        
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Requested answer matrix file no longer exists in storage registry.")
        
    return FileResponse(
        path=file_path, 
        media_type='application/pdf', 
        filename=filename
    )