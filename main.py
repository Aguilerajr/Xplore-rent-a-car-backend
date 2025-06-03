from fastapi import FastAPI, Form, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os
from datetime import datetime
from pydantic import BaseModel
import re
import io
import barcode
from barcode.writer import ImageWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from contextlib import asynccontextmanager

# BASES DE DATOS
DATABASE_URL = "postgresql://postgres:bgNLRBzPghPvzlMkAROLGTIrNlBcaVgt@crossover.proxy.rlwy.net:11506/railway"
DATABASE_URL_EMPLEADOS = "postgresql://postgres:gFQOssQuCNFeLZqvKBNcERsRrxWEiZlJ@shuttle.proxy.rlwy.net:42664/railway"

engine = create_engine(DATABASE_URL)
engine_empleados = create_engine(DATABASE_URL_EMPLEADOS)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionEmpleados = sessionmaker(autocommit=False, autoflush=False, bind=engine_empleados)
Base = declarative_base()
BaseEmpleados = declarative_base()

# MODELOS BASE DE VEHÍCULOS
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
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo_vehiculo = Column(String)
    clasificacion = Column(String)
    fecha = Column(DateTime, default=datetime.utcnow)
    semana = Column(Integer)
    estado = Column(String)

class RegistroLavado(Base):
    __tablename__ = "registros_lavado"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vehiculo = Column(String)
    empleado = Column(String)
    inicio = Column(DateTime)
    fin = Column(DateTime)
    tiempo_real = Column(Integer)
    tiempo_estimado = Column(Integer)
    eficiencia = Column(String)

# MODELO BASE DE EMPLEADOS
class Empleado(BaseEmpleados):
    __tablename__ = "empleados"
    codigo = Column(String(4), primary_key=True)
    nombre = Column(String, nullable=True)

# Tiempos estimados por clasificación
TIEMPOS_ESTIMADOS = {
    "A1": 120, "A2": 60, "A3": 30, "A4": 240, "A5": 7,
    "B1": 100, "B2": 50, "B3": 25, "B4": 240, "B5": 7,
    "C1": 100, "C2": 60, "C3": 30, "C4": 240, "C5": 7,
    "D1": 120, "D2": 60, "D3": 30, "D4": 240, "D5": 7,
    "E1": 90, "E2": 60, "E3": 40, "E4": 240, "E5": 7,
    "F1": 50, "F2": 35, "F3": 20, "F4": 240, "F5": 7
}

# Inicialización
def init_db():
    db = SessionLocal()
    try:
        iniciales = ["CAR001", "CAR002", "VEH0003", "VEH0004"]
        for cod in iniciales:
            if not db.query(Vehiculo).filter_by(codigo=cod).first():
                db.add(Vehiculo(codigo=cod))
        db.commit()
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    BaseEmpleados.metadata.create_all(bind=engine_empleados)
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

# Directorios para plantillas y estáticos
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Sesiones
def get_db():  # Para vehículos
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_empleados():  # Para empleados
    db = SessionEmpleados()
    try:
        yield db
    finally:
        db.close()

# 🔷 Endpoint para verificar empleado (login)
@app.get("/verificar_empleado")
def verificar_empleado(codigo: str, db: Session = Depends(get_db_empleados)):
    existe = db.query(Empleado).filter_by(codigo=codigo).first()
    return {"valido": bool(existe)}

# 🔷 Las demás rutas (calidad, clasificar, registrar, etc.) quedan exactamente igual a lo que ya tienes…

# 🔷 RUTAS DE EMPLEADOS (agregar empleado HTML)
@app.get("/agregar_empleado", response_class=HTMLResponse)
def mostrar_formulario_empleado(request: Request):
    return templates.TemplateResponse("agregar_empleado.html", {"request": request, "mensaje": ""})

@app.post("/agregar_empleado", response_class=HTMLResponse)
def agregar_empleado(request: Request, codigo: str = Form(...), nombre: str = Form(...), db: Session = Depends(get_db_empleados)):
    if not re.fullmatch(r"\d{4}", codigo):
        mensaje = "❌ El código debe tener 4 dígitos numéricos."
    elif db.query(Empleado).filter_by(codigo=codigo).first():
        mensaje = "❌ El empleado ya existe."
    else:
        db.add(Empleado(codigo=codigo, nombre=nombre))
        db.commit()
        mensaje = f"✅ Empleado {nombre} agregado con código {codigo}."
    return templates.TemplateResponse("agregar_empleado.html", {"request": request, "mensaje": mensaje})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
