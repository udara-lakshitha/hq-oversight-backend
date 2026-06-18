from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.main.database import Base

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone_number = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    profile_pic_path = Column(String, nullable=True)

    devices = relationship("StudentDevice", back_populates="student", cascade="all, delete-orphan")
    marks = relationship("EvaluationMark", back_populates="student", cascade="all, delete-orphan")


class StudentDevice(Base):
    __tablename__ = "student_devices"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    device_token = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    student = relationship("Student", back_populates="devices")


class EvaluationMark(Base):
    __tablename__ = "evaluation_marks"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    
    paper_number = Column(String, index=True, nullable=False)  # Handles your Pure/Applied grouping implicitly
    marks = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    student = relationship("Student", back_populates="marks")