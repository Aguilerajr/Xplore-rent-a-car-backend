from fastapi import FastAPI, Form, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from contextlib import asynccontextmanager
import barcode
from barcode.writer import ImageWriter
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import re

# BASES DE DATOS
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://...")
DATABASE_URL_EMPLEADOS = os.getenv("DATABASE_URL_EMPLEADOS", "postgresql://...")

engine = create_engine(DATABASE_URL)
engine_empleados = create_engine(DATABASE_URL_EMPLEADOS)
SessionLocal = sessionmaker(bind=engine)
SessionEmpleados = sessionmaker(bind=engine_empleados)
Base = declarative_base()
BaseEmpleados = declarative_base()

# Modelos
class Vehiculo(Base):
    __tablename__ = "vehiculos"
    codigo = Column(String, primary_key=True)

class Clasificacion(Base):
    __tablename__ = "clasificaciones"
    codigo = Column(String, primary_key=True)
    clasificacion = Column(String)
    revisado_por = Column(String)
    tiempo_estimado = Column(Integer)

class ColaLavado(Base):
    __tablename__ = "cola_lavado"
    id = Column(Integer, primary_key=True)
    codigo_vehiculo = Column(String)
    clasificacion = Column(String)
    fecha = Column(DateTime)
    semana = Column(Integer)
    estado = Column(String)

class RegistroLavado(Base):
    __tablename__ = "registros_lavado"
    id = Column(Integer, primary_key=True)
    vehiculo = Column(String)
    empleado = Column(String)
    inicio = Column(DateTime)
    fin = Column(DateTime)
    tiempo_real = Column(Integer)
    tiempo_estimado = Column(Integer)
    eficiencia = Column(String)

class Empleado(BaseEmpleados):
    __tablename__ = "empleados"
    codigo = Column(String, primary_key=True)
    nombre = Column(String)

# App
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    BaseEmpleados.metadata.create_all(bind=engine_empleados)
    yield

app = FastAPI(lifespan=lifespan)
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Dependencias
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_empleados():
    db = SessionEmpleados()
    try:
        yield db
    finally:
        db.close()

# ENDPOINT CRÍTICO QUE FALLA
@app.post("/registrar")
def registrar_lavado(
    codigo: str = Form(...),
    empleado: str = Form(...),
    inicio: str = Form(...),
    fin: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        inicio_dt = datetime.fromisoformat(inicio)
        fin_dt = datetime.fromisoformat(fin)
        tiempo_real = int((fin_dt - inicio_dt).total_seconds() / 60)
        clasificacion = db.query(Clasificacion).filter_by(codigo=codigo).first()
        if not clasificacion:
            return {"error": "El vehículo no ha sido clasificado"}
        tiempo_estimado = clasificacion.tiempo_estimado
        eficiencia = round((tiempo_estimado / tiempo_real) * 100, 1) if tiempo_real > 0 else 0
        db.add(RegistroLavado(
            vehiculo=codigo,
            empleado=empleado,
            inicio=inicio_dt,
            fin=fin_dt,
            tiempo_real=tiempo_real,
            tiempo_estimado=tiempo_estimado,
            eficiencia=f"{eficiencia}%"
        ))
        db.query(ColaLavado).filter(ColaLavado.codigo_vehiculo == codigo).update({"estado": "completado"})
        db.commit()
        return {"status": "ok", "eficiencia": eficiencia}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
