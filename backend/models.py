import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="inspector")  # e.g., inspector, administrator
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    inspections = relationship("Inspection", back_populates="inspector", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    owner = relationship("User", back_populates="projects")
    inspections = relationship("Inspection", back_populates="project", cascade="all, delete-orphan")


class Inspection(Base):
    __tablename__ = "inspections"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    raw_image_path = Column(String, nullable=False)
    mask_path = Column(String, nullable=False)
    skeleton_path = Column(String, nullable=False)
    max_width_mm = Column(Float, nullable=False)
    length_mm = Column(Float, nullable=False)
    severity = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    inspector = relationship("User", back_populates="inspections")
    project = relationship("Project", back_populates="inspections")


class ModelTraining(Base):
    __tablename__ = "model_trainings"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="queued")  # queued, running, completed, failed
    epochs = Column(Integer, default=10)
    current_epoch = Column(Integer, default=0)
    loss = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    logs = Column(Text, default="")
    model_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
