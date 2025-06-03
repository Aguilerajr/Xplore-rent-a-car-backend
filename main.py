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
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:bgNLRBzPghPvzlMkAROLGTIrNlBcaVgt@crossover.proxy.rlwy.net:11506/railway")
DATABASE_URL_EMPLEADOS = "postgresql://postgres:gFQOssQuCNFeLZqvKBNcERsRrxWEiZlJ@shuttle.proxy.rlwy.net:42664/railway"

engine = create_engine(DATABASE_URL)
engine_empleados = create_engine(DATABASE_URL_EMPLEADOS)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionEmpleados = sessionmaker(autocommit=False, autoflush=False, bind=engine_empleados)
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
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

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
        iniciales = ["CAR001", "CAR002", "VEH0003", "VEH0004"]
        for cod in iniciales:
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
    disponibles = [cod for cod in codigos if cod not in {c[0] for c in completados}]
    db.close()
    return templates.TemplateResponse("calidad.html", {"request": request, "vehiculos": disponibles, "mensaje": ""})

@app.get("/buscar_codigos")
def buscar_codigos(q: str, db: Session = Depends(get_db)):
    resultados = db.query(Vehiculo.codigo).filter(Vehiculo.codigo.like(f"{q}%")).all()
    return {"resultados": [r[0] for r in resultados]}

@app.get("/agregar_vehiculo", response_class=HTMLResponse)
def mostrar_formulario_agregar(request: Request):
    return templates.TemplateResponse("agregar_vehiculo.html", {"request": request, "mensaje": ""})

@app.post("/agregar_vehiculo", response_class=HTMLResponse)
def procesar_agregar_vehiculo(request: Request, letra: str = Form(...), digitos: str = Form(...), db: Session = Depends(get_db)):
    letra = letra.upper()
    if letra not in ["P", "C", "M", "T"]:
        mensaje = "❌ Letra inválida."
    elif not re.fullmatch(r"\d{4}", digitos):
        mensaje = "❌ Los dígitos deben tener 4 números."
    else:
        codigo = f"{letra}-{digitos}"
        if db.query(Vehiculo).filter_by(codigo=codigo).first():
            mensaje = "❌ Ya existe."
        else:
            db.add(Vehiculo(codigo=codigo))
            db.commit()
            mensaje = f"✅ {codigo} agregado."
    return templates.TemplateResponse("agregar_vehiculo.html", {"request": request, "mensaje": mensaje})

@app.get("/crear_codigos", response_class=HTMLResponse)
def mostrar_creador_codigos(request: Request):
    return templates.TemplateResponse("crear_codigos.html", {"request": request})

@app.post("/crear_codigos/generar")
async def generar_codigo_barras(request: Request, codigo: str = Form(...)):
    buffer = io.BytesIO()
    code128 = barcode.get_barcode_class("code128")(codigo, writer=ImageWriter())
    code128.write(buffer)
    buffer.seek(0)
    headers = {"Content-Disposition": f"attachment; filename={codigo}.png"}
    return StreamingResponse(buffer, media_type="image/png", headers=headers)

@app.get("/crear_codigos/generar_todos")
async def generar_todos_codigos(db: Session = Depends(get_db)):
    codigos = [v.codigo for v in db.query(Vehiculo).all()]
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    y = letter[1] - 50
    for codigo in codigos:
        b_buf = io.BytesIO()
        barcode.get_barcode_class("code128")(codigo, writer=ImageWriter()).write(b_buf)
        b_buf.seek(0)
        c.drawImage(ImageReader(b_buf), 50, y - 50, width=300, height=50)
        c.drawString(50, y - 60, codigo)
        y -= 100
        if y < 100:
            c.showPage()
            y = letter[1] - 50
    c.save()
    buffer.seek(0)
    headers = {"Content-Disposition": "attachment; filename=codigos_vehiculos.pdf"}
    return StreamingResponse(buffer, media_type="application/pdf", headers=headers)

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

@app.get("/agregar_empleado", response_class=HTMLResponse)
def mostrar_formulario_empleado(request: Request):
    return templates.TemplateResponse("agregar_empleado.html", {"request": request, "mensaje": ""})

@app.post("/agregar_empleado", response_class=HTMLResponse)
def agregar_empleado(request: Request, codigo: str = Form(...), nombre: str = Form(...), db: Session = Depends(get_db_empleados)):
    if not re.fullmatch(r"\d{4}", codigo):
        mensaje = "❌ Código inválido."
    elif db.query(Empleado).filter_by(codigo=codigo).first():
        mensaje = "❌ Ya existe."
    else:
        db.add(Empleado(codigo=codigo, nombre=nombre))
        db.commit()
        mensaje = f"✅ Empleado {nombre} registrado."
    return templates.TemplateResponse("agregar_empleado.html", {"request": request, "mensaje": mensaje})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
