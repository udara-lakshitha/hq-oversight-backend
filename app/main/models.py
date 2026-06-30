from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.main.database import Base

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone_number = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    profile_pic_path = Column(String, nullable=True)
    role = Column(String)

    devices = relationship("StudentDevice", back_populates="student", cascade="all, delete-orphan")
    marks = relationship("EvaluationMark", back_populates="student", cascade="all, delete-orphan")
    submissions = relationship("ExamSubmission", back_populates="student", cascade="all, delete-orphan")


class StudentDevice(Base):
    __tablename__ = "student_devices"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    device_token = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    student = relationship("Student", back_populates="devices")


class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    paper_number = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    paper_type = Column(String, nullable=False)
    question_file_path = Column(String, nullable=False)
    marking_scheme_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    submissions = relationship("ExamSubmission", back_populates="exam", cascade="all, delete-orphan")
    marks = relationship("EvaluationMark", back_populates="exam", cascade="all, delete-orphan") # Linked here!


class ExamSubmission(Base):
    __tablename__ = "exam_submissions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False)
    submitted_file_path = Column(String, nullable=False)
    submitted_at = Column(DateTime, default=datetime.now)

    student = relationship("Student", back_populates="submissions")
    exam = relationship("Exam", back_populates="submissions")


class EvaluationMark(Base):
    __tablename__ = "evaluation_marks"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False)
    marks = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    student = relationship("Student", back_populates="marks")
    exam = relationship("Exam", back_populates="marks")