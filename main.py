from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import os

from database import get_db, init_db, Cylinder, LevelRecord
from calculations import calculate_liquid_level


app = FastAPI(title="高压气体钢瓶液位监测系统", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SensorDataRequest(BaseModel):
    cylinder_code: str
    echo_time_us: float
    temperature: float
    liquid_type: Optional[str] = "generic"


class LevelRecordResponse(BaseModel):
    id: int
    cylinder_code: str
    echo_time_us: float
    temperature: float
    liquid_level: float
    level_percentage: float
    sound_velocity: float
    recorded_at: datetime


class CylinderStatusResponse(BaseModel):
    id: int
    cylinder_code: str
    material: str
    wall_thickness: float
    total_height: float
    inner_diameter: float
    last_level: Optional[float] = None
    last_percentage: Optional[float] = None
    last_temperature: Optional[float] = None
    last_recorded_at: Optional[datetime] = None


@app.on_event("startup")
def on_startup():
    init_db()


@app.post("/api/sensor-data", response_model=LevelRecordResponse, summary="接收超声波传感器数据")
def receive_sensor_data(
    data: SensorDataRequest,
    db: Session = Depends(get_db),
):
    """
    接收超声波传感器的回波时间数据，计算液位并存入数据库

    - **cylinder_code**: 钢瓶编号
    - **echo_time_us**: 超声波回波时间（微秒）
    - **temperature**: 当前温度（摄氏度）
    - **liquid_type**: 液化气体类型（默认 generic）
    """
    cylinder = (
        db.query(Cylinder).filter(Cylinder.cylinder_code == data.cylinder_code).first()
    )
    if not cylinder:
        raise HTTPException(
            status_code=404, detail=f"钢瓶编号 {data.cylinder_code} 不存在"
        )

    if data.echo_time_us <= 0:
        raise HTTPException(status_code=400, detail="回波时间必须为正数")

    if cylinder.wall_thickness <= 0 or cylinder.total_height <= 0 or cylinder.inner_diameter <= 0:
        raise HTTPException(
            status_code=500,
            detail=f"钢瓶 {data.cylinder_code} 参数异常，请检查壁厚、总高度、内径是否均为正数"
        )

    result = calculate_liquid_level(
        echo_time_us=data.echo_time_us,
        material=cylinder.material,
        wall_thickness=cylinder.wall_thickness,
        total_height=cylinder.total_height,
        temperature=data.temperature,
        liquid_type=data.liquid_type,
    )

    record = LevelRecord(
        cylinder_id=cylinder.id,
        echo_time_us=data.echo_time_us,
        temperature=data.temperature,
        liquid_level=result.liquid_level,
        level_percentage=result.level_percentage,
        sound_velocity=result.liquid_sound_velocity,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return LevelRecordResponse(
        id=record.id,
        cylinder_code=cylinder.cylinder_code,
        echo_time_us=record.echo_time_us,
        temperature=record.temperature,
        liquid_level=record.liquid_level,
        level_percentage=record.level_percentage,
        sound_velocity=record.sound_velocity,
        recorded_at=record.recorded_at,
    )


@app.get("/api/cylinders", response_model=List[CylinderStatusResponse], summary="获取所有钢瓶及最新液位状态")
def get_all_cylinders(
    db: Session = Depends(get_db),
):
    """
    获取所有钢瓶的基本信息及其最新一次液位记录
    """
    cylinders = db.query(Cylinder).all()
    results = []

    for cyl in cylinders:
        last_record = (
            db.query(LevelRecord)
            .filter(LevelRecord.cylinder_id == cyl.id)
            .order_by(desc(LevelRecord.recorded_at))
            .first()
        )

        resp = CylinderStatusResponse(
            id=cyl.id,
            cylinder_code=cyl.cylinder_code,
            material=cyl.material,
            wall_thickness=cyl.wall_thickness,
            total_height=cyl.total_height,
            inner_diameter=cyl.inner_diameter,
        )

        if last_record:
            resp.last_level = last_record.liquid_level
            resp.last_percentage = last_record.level_percentage
            resp.last_temperature = last_record.temperature
            resp.last_recorded_at = last_record.recorded_at

        results.append(resp)

    return results


@app.get(
    "/api/cylinders/{cylinder_code}/records",
    response_model=List[LevelRecordResponse],
    summary="获取指定钢瓶的历史液位记录",
)
def get_cylinder_records(
    cylinder_code: str,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    获取指定钢瓶的历史液位记录，按时间倒序排列

    - **cylinder_code**: 钢瓶编号
    - **limit**: 返回记录条数（默认100，最大1000）
    """
    cylinder = (
        db.query(Cylinder).filter(Cylinder.cylinder_code == cylinder_code).first()
    )
    if not cylinder:
        raise HTTPException(
            status_code=404, detail=f"钢瓶编号 {cylinder_code} 不存在"
        )

    records = (
        db.query(LevelRecord)
        .filter(LevelRecord.cylinder_id == cylinder.id)
        .order_by(desc(LevelRecord.recorded_at))
        .limit(limit)
        .all()
    )

    return [
        LevelRecordResponse(
            id=r.id,
            cylinder_code=cylinder.cylinder_code,
            echo_time_us=r.echo_time_us,
            temperature=r.temperature,
            liquid_level=r.liquid_level,
            level_percentage=r.level_percentage,
            sound_velocity=r.sound_velocity,
            recorded_at=r.recorded_at,
        )
        for r in records
    ]


@app.post("/api/cylinders", summary="新增钢瓶信息")
def create_cylinder(
    cylinder_code: str,
    material: str,
    wall_thickness: float,
    total_height: float,
    inner_diameter: float,
    db: Session = Depends(get_db),
):
    """
    注册新的钢瓶信息

    - **cylinder_code**: 钢瓶编号（唯一）
    - **material**: 材质 (steel, aluminum, stainless_steel, copper)
    - **wall_thickness**: 壁厚（米）
    - **total_height**: 内部总高度（米）
    - **inner_diameter**: 内部直径（米）
    """
    existing = (
        db.query(Cylinder).filter(Cylinder.cylinder_code == cylinder_code).first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail=f"钢瓶编号 {cylinder_code} 已存在"
        )

    cyl = Cylinder(
        cylinder_code=cylinder_code,
        material=material,
        wall_thickness=wall_thickness,
        total_height=total_height,
        inner_diameter=inner_diameter,
    )
    db.add(cyl)
    db.commit()
    db.refresh(cyl)

    return {
        "message": "钢瓶信息已添加",
        "cylinder": {
            "id": cyl.id,
            "cylinder_code": cyl.cylinder_code,
            "material": cyl.material,
        },
    }


if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def read_root():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {
        "name": "高压气体钢瓶液位监测系统",
        "version": "1.0.0",
        "docs": "/docs",
    }
