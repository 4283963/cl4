from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./cylinder_monitor.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Cylinder(Base):
    __tablename__ = "cylinders"

    id = Column(Integer, primary_key=True, index=True)
    cylinder_code = Column(String, unique=True, index=True, nullable=False)
    material = Column(String, nullable=False)
    wall_thickness = Column(Float, nullable=False)
    total_height = Column(Float, nullable=False)
    inner_diameter = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    records = relationship("LevelRecord", back_populates="cylinder")


class LevelRecord(Base):
    __tablename__ = "level_records"

    id = Column(Integer, primary_key=True, index=True)
    cylinder_id = Column(Integer, ForeignKey("cylinders.id"), nullable=False)
    echo_time_us = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    liquid_level = Column(Float, nullable=False)
    level_percentage = Column(Float, nullable=False)
    sound_velocity = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    cylinder = relationship("Cylinder", back_populates="records")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(Cylinder).count()
        if existing == 0:
            sample_cylinders = [
                Cylinder(
                    cylinder_code="CYL-001",
                    material="steel",
                    wall_thickness=0.008,
                    total_height=1.5,
                    inner_diameter=0.4,
                ),
                Cylinder(
                    cylinder_code="CYL-002",
                    material="steel",
                    wall_thickness=0.008,
                    total_height=1.5,
                    inner_diameter=0.4,
                ),
                Cylinder(
                    cylinder_code="CYL-003",
                    material="aluminum",
                    wall_thickness=0.010,
                    total_height=1.2,
                    inner_diameter=0.35,
                ),
                Cylinder(
                    cylinder_code="CYL-004",
                    material="steel",
                    wall_thickness=0.008,
                    total_height=1.8,
                    inner_diameter=0.5,
                ),
            ]
            db.add_all(sample_cylinders)
            db.commit()
    finally:
        db.close()
