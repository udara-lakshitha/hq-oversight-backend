import os
import secrets
import io
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.main.database import get_db
from app.main import models, schemas
from app.main.routers.auth import get_current_student
from app.main.routers.exams import get_biweekly_schedule_state
from app.utils.storage import upload_file_to_supabase, get_file_from_supabase

router = APIRouter(prefix="/api/marks", tags=["Evaluation Marks Engine"])

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
        scheme_exists = bool(exam.marking_scheme_path)
        
        matching_mark = db.query(models.EvaluationMark).filter(
            models.EvaluationMark.student_id == current_student.id,
            models.EvaluationMark.exam_id == exam.id
        ).first()
        
        feedback_exists = bool(matching_mark and matching_mark.feedback_file_path)

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
        q_bytes = await question_file.read()
        random_hex = secrets.token_hex(4)
        q_filename = f"{prefix}_question_{random_hex}_{question_file.filename}"
        
        storage_path = upload_file_to_supabase(q_bytes, q_filename, folder="questions")
        exam.question_file_path = storage_path

    if marking_scheme_file and marking_scheme_file.filename:
        m_bytes = await marking_scheme_file.read()
        random_hex = secrets.token_hex(4)
        m_filename = f"{prefix}_scheme_{random_hex}_{marking_scheme_file.filename}"
        
        storage_path = upload_file_to_supabase(m_bytes, m_filename, folder="schemes")
        exam.marking_scheme_path = storage_path

    exam.title = title
    exam.paper_type = paper_type

    db.commit()
    return {"message": f"Successfully updated and processed assets for {paper_number}."}


@router.get("/admin/pending-submissions")
def admin_get_pending_submissions(db: Session = Depends(get_db)):
    pending_list = []
    submissions = db.query(models.ExamSubmission).all()

    for sub in submissions:
        student = db.query(models.Student).filter(models.Student.id == sub.student_id).first()
        exam = db.query(models.Exam).filter(models.Exam.id == sub.exam_id).first()
        
        if student and exam:
            already_marked = db.query(models.EvaluationMark).filter(
                models.EvaluationMark.student_id == sub.student_id,
                models.EvaluationMark.exam_id == sub.exam_id
            ).first()

            if not already_marked:
                filename = os.path.basename(sub.submitted_file_path)
                pending_list.append({
                    "submission_id": f"{sub.student_id}_{sub.exam_id}",
                    "student_id": sub.student_id,
                    "student_name": student.name,
                    "exam_id": sub.exam_id,
                    "paper_number": exam.paper_number,
                    "filename": filename
                })
                
    return pending_list

@router.get("/admin/download-submission/{filename}")
def admin_download_student_submission(filename: str, db: Session = Depends(get_db)):
    submission = db.query(models.ExamSubmission).filter(
        models.ExamSubmission.submitted_file_path.like(f"%{filename}")
    ).first()

    if not submission or not submission.submitted_file_path:
        raise HTTPException(status_code=404, detail="Requested answer matrix file no longer exists in storage registry.")
        
    try:
        file_bytes = get_file_from_supabase(submission.submitted_file_path)
        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename={filename}"}
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Requested file path does not exist in Cloud Storage arrays.")


@router.post("/admin/submit-evaluation")
async def admin_submit_evaluation(
    student_id: int = Form(...),
    exam_id: int = Form(...),
    marks: float = Form(...),
    feedback_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    f_bytes = await feedback_file.read()
    random_hex = secrets.token_hex(4)
    feedback_filename = f"feedback_stu_{student_id}_exam_{exam_id}_{random_hex}.pdf"
    storage_path = upload_file_to_supabase(f_bytes, feedback_filename, folder="feedback")
        
    evaluation = db.query(models.EvaluationMark).filter(
        models.EvaluationMark.student_id == student_id,
        models.EvaluationMark.exam_id == exam_id
    ).first()
    
    if evaluation:
        evaluation.marks = marks
        evaluation.feedback_file_path = storage_path
    else:
        new_mark = models.EvaluationMark(
            student_id=student_id,
            exam_id=exam_id,
            marks=marks,
            feedback_file_path=storage_path
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