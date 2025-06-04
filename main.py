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
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:bgNLRBzPghPvzlMkAROLGTIrNlBcaVgt@crossover.proxy.rlwy.net:11506/railway")
DATABASE_URL_EMPLEADOS = "postgresql://postgres:gFQOssQuCNFeLZqvKBNcERsRrxWEiZlJ@shuttle.proxy.rlwy.net:42664/railway"

engine = create_engine(DATABASE_URL)
engine_empleados = create_engine(DATABASE_URL_EMPLEADOS)
SessionLocal = sessionmaker(bind=engine)
SessionEmpleados = sessionmaker(bind=engine_empleados)
Base = declarative_base()
BaseEmpleados = declarative_base()

TIEMPOS_ESTIMADOS = {
    "A1": 120, "A2": 60, "A3": 30, "A4": 240, "A5": 7,
    "B1": 100, "B2": 50, "B3": 25, "B4": 240, "B5": 7,
    "C1": 100, "C2": 60, "C3": 30, "C4": 240, "C5": 7,
    "D1": 120, "D2": 60, "D3": 30, "D4": 240, "D5": 7,
    "E1": 90, "E2": 60, "E3": 40, "E4": 240, "E5": 7,
    "F1": 50, "F2": 35, "F3": 20, "F4": 240, "F5": 7
}

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
    codigo = Column(String(4), primary_key=True)
    nombre = Column(String)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    BaseEmpleados.metadata.create_all(bind=engine_empleados)
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

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

def init_db():
    db = SessionLocal()
    try:
        for cod in ["CAR001", "CAR002", "VEH0003", "VEH0004"]:
            if not db.query(Vehiculo).filter_by(codigo=cod).first():
                db.add(Vehiculo(codigo=cod))
        db.commit()
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/calidad", response_class=HTMLResponse)
def mostrar_formulario(request: Request):
    db = SessionLocal()
    vehiculos = db.query(Vehiculo.codigo).all()
    codigos = [v[0] for v in vehiculos]
    completados = db.query(ColaLavado.codigo_vehiculo).filter(ColaLavado.estado == "completado").all()
    disponibles = [c for c in codigos if c not in {x[0] for x in completados}]
    db.close()
    return templates.TemplateResponse("calidad.html", {"request": request, "vehiculos": disponibles, "mensaje": ""})

@app.post("/clasificar", response_class=HTMLResponse)
def clasificar_vehiculo(request: Request, codigo: str = Form(...), suciedad: str = Form(...), tipo: str = Form(...), db: Session = Depends(get_db)):
    clasificacion_map = {"Muy sucio": "1", "Normal": "2", "Poco sucio": "3", "Shampuseado": "4", "Franeleado": "5"}
    tipo_map = {"Camioneta Grande": "A", "Camioneta pequeña": "B", "Busito": "C", "Pick Up": "D", "Turismo normal": "E", "Turismo pequeño": "F"}
    grado = clasificacion_map.get(suciedad)
    tipo_vehiculo = tipo_map.get(tipo)
    if not grado or not tipo_vehiculo:
        mensaje = "❌ Clasificación inválida"
    else:
        clasificacion = tipo_vehiculo + grado
        tiempo_estimado = TIEMPOS_ESTIMADOS.get(clasificacion, 18)
        db.query(Clasificacion).filter(Clasificacion.codigo == codigo).delete()
        db.add(Clasificacion(codigo=codigo, clasificacion=clasificacion, revisado_por="Calidad", tiempo_estimado=tiempo_estimado))
        db.query(ColaLavado).filter(ColaLavado.codigo_vehiculo == codigo, ColaLavado.estado == "completado").delete()
        db.add(ColaLavado(codigo_vehiculo=codigo, clasificacion=clasificacion, fecha=datetime.utcnow(), semana=datetime.utcnow().isocalendar()[1], estado="en_cola"))
        db.commit()
        mensaje = f"✅ {codigo} clasificado como {suciedad} - {tipo} ({clasificacion})"
    vehiculos = db.query(Vehiculo.codigo).all()
    codigos = [v[0] for v in vehiculos]
    completados = db.query(ColaLavado.codigo_vehiculo).filter(ColaLavado.estado == "completado").all()
    disponibles = [c for c in codigos if c not in {x[0] for x in completados}]
    return templates.TemplateResponse("calidad.html", {"request": request, "vehiculos": disponibles, "mensaje": mensaje})

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

@app.post("/login")
def login(codigo: str = Form(...), db: Session = Depends(get_db_empleados)):
    empleado = db.query(Empleado).filter_by(codigo=codigo).first()
    if empleado:
        return {"status": "ok", "codigo": empleado.codigo, "nombre": empleado.nombre}
    return {"status": "error", "message": "Código no válido"}

@app.get("/obtener_empleado")
def obtener_empleado(codigo: str, db: Session = Depends(get_db_empleados)):
    empleado = db.query(Empleado).filter_by(codigo=codigo).first()
    if empleado:
        return {"codigo": empleado.codigo, "nombre": empleado.nombre}
    return JSONResponse(content={"detail": "No encontrado"}, status_code=404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
