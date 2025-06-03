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

# RUTAS
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/calidad", response_class=HTMLResponse)
def mostrar_formulario(request: Request):
    db = SessionLocal()
    vehiculos = db.query(Vehiculo.codigo).all()
    codigos = [v[0] for v in vehiculos]
    completados = db.query(ColaLavado.codigo_vehiculo).filter(ColaLavado.estado == "completado").all()
    completados_set = {c[0] for c in completados}
    disponibles = [cod for cod in codigos if cod not in completados_set]
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
    completados_set = {c[0] for c in completados}
    disponibles = [cod for cod in codigos if cod not in completados_set]
    return templates.TemplateResponse("calidad.html", {"request": request, "vehiculos": disponibles, "mensaje": mensaje})

class RegistroEntrada(BaseModel):
    vehiculo: str
    empleado: str

@app.post("/registrar")
def registrar_evento(entrada: RegistroEntrada, db: Session = Depends(get_db)):
    vehiculo = entrada.vehiculo
    empleado = entrada.empleado
    ahora = datetime.utcnow()
    clasif = db.query(Clasificacion).filter(Clasificacion.codigo == vehiculo).first()
    if not clasif:
        return JSONResponse(content={"status": "error", "message": "Vehículo no clasificado"}, status_code=400)
    registro_abierto_otro = db.query(RegistroLavado).filter(RegistroLavado.empleado == empleado, RegistroLavado.fin.is_(None), RegistroLavado.vehiculo != vehiculo).first()
    if registro_abierto_otro:
        return JSONResponse(content={"status": "error", "message": f"{empleado} ya tiene un check-in en otro vehículo"}, status_code=400)
    registro_abierto = db.query(RegistroLavado).filter(RegistroLavado.vehiculo == vehiculo, RegistroLavado.empleado == empleado, RegistroLavado.fin.is_(None)).first()
    if registro_abierto:
        registro_abierto.fin = ahora
        tiempo_real = int((ahora - registro_abierto.inicio).total_seconds() / 60)
        tiempo_estimado = clasif.tiempo_estimado or 18
        eficiencia = f"{int((tiempo_estimado / tiempo_real) * 100)}%" if tiempo_real else "N/A"
        registro_abierto.tiempo_real = tiempo_real
        registro_abierto.tiempo_estimado = tiempo_estimado
        registro_abierto.eficiencia = eficiencia
        db.commit()
        otros_trabajando = db.query(RegistroLavado).filter(RegistroLavado.vehiculo == vehiculo, RegistroLavado.fin.is_(None), RegistroLavado.id != registro_abierto.id).first()
        if not otros_trabajando:
            db.query(ColaLavado).filter(ColaLavado.codigo_vehiculo == vehiculo).delete()
            db.query(Clasificacion).filter(Clasificacion.codigo == vehiculo).delete()
            db.commit()
        return {"status": "checkout", "vehiculo": vehiculo, "empleado": empleado, "fin": ahora.isoformat(), "mensaje": f"✅ Check-out realizado para {vehiculo}"}
    nuevo_registro = RegistroLavado(vehiculo=vehiculo, empleado=empleado, inicio=ahora, tiempo_estimado=clasif.tiempo_estimado or 18)
    db.add(nuevo_registro)
    db.commit()
    return {"status": "checkin", "vehiculo": vehiculo, "empleado": empleado, "inicio": ahora.isoformat(), "mensaje": f"🚗 Check-in registrado para {vehiculo}"}

# 🔷 RUTAS DE EMPLEADOS (usando la otra base de datos)
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

# 🔷 Las demás rutas (`agregar_vehiculo`, `crear_codigos`, `buscar_codigos`, etc.) quedan iguales...

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
