from fastapi import FastAPI, Form, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pathlib import Path
from datetime import datetime
import os
import io
import re

# Librerías para códigos de barras
import barcode
from barcode.writer import ImageWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

# Base de datos principal (vehículos)
# BASE DE DATOS VEHÍCULOS
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:bgNLRBzPghPvzlMkAROLGTIrNlBcaVgt@crossover.proxy.rlwy.net:11506/railway")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# BASE DE DATOS EMPLEADOS
DATABASE_URL_EMPLEADOS = os.getenv("DATABASE_URL_EMPLEADOS", "postgresql://postgres:gFQOssQuCNFeLZqvKBNcERsRrxWEiZlJ@shuttle.proxy.rlwy.net:42664/railway")
engine_empleados = create_engine(DATABASE_URL_EMPLEADOS)
SessionEmpleados = sessionmaker(autocommit=False, autoflush=False, bind=engine_empleados)
BaseEmpleados = declarative_base()

# FastAPI app
app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

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
    fecha = Column(DateTime, default=datetime.utcnow)
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

# Tiempos estimados
TIEMPOS_ESTIMADOS = {
    "A1": 120, "A2": 60, "A3": 30, "A4": 240, "A5": 7,
    "B1": 100, "B2": 50, "B3": 25, "B4": 240, "B5": 7,
    "C1": 100, "C2": 60, "C3": 30, "C4": 240, "C5": 7,
    "D1": 120, "D2": 60, "D3": 30, "D4": 240, "D5": 7,
    "E1": 90,  "E2": 60, "E3": 40, "E4": 240, "E5": 7,
    "F1": 50,  "F2": 35, "F3": 20, "F4": 240, "F5": 7
}

# Dependencias DB
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

# Rutas
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/calidad", response_class=HTMLResponse)
def calidad(request: Request):
    return templates.TemplateResponse("calidad.html", {"request": request})

@app.post("/clasificar", response_class=HTMLResponse)
def clasificar(request: Request, codigo: str = Form(...), suciedad: str = Form(...), tipo: str = Form(...), db: Session = Depends(get_db)):
    clasificacion_map = {"Muy sucio": "1", "Normal": "2", "Poco sucio": "3", "Shampuseado": "4", "Franeleado": "5"}
    tipo_map = {"Camioneta Grande": "A", "Camioneta pequeña": "B", "Busito": "C", "Pick Up": "D", "Turismo normal": "E", "Turismo pequeño": "F"}

    grado = clasificacion_map.get(suciedad, "")
    tipo_letra = tipo_map.get(tipo, "")
    clasificacion = tipo_letra + grado
    tiempo_estimado = TIEMPOS_ESTIMADOS.get(clasificacion, 18)

    db.add(Clasificacion(codigo=codigo, clasificacion=clasificacion, revisado_por="calidad", tiempo_estimado=tiempo_estimado))
    db.commit()

    return templates.TemplateResponse("calidad.html", {"request": request, "mensaje": f"✅ {codigo} clasificado como {clasificacion}"})

@app.get("/buscar_codigos")
def buscar_codigos(q: str, db: Session = Depends(get_db)):
    resultados = db.query(Vehiculo.codigo).filter(Vehiculo.codigo.like(f"{q}%")).all()
    return {"resultados": [r[0] for r in resultados]}

@app.get("/agregar_empleado", response_class=HTMLResponse)
def form_empleado(request: Request):
    return templates.TemplateResponse("agregar_empleado.html", {"request": request})

@app.post("/agregar_empleado", response_class=HTMLResponse)
def agregar_empleado(request: Request, codigo: str = Form(...), nombre: str = Form(...), db: Session = Depends(get_db_empleados)):
    db.add(Empleado(codigo=codigo, nombre=nombre))
    db.commit()
    return templates.TemplateResponse("agregar_empleado.html", {"request": request, "mensaje": "Empleado agregado correctamente"})

@app.get("/crear_codigos", response_class=HTMLResponse)
def crear_codigos(request: Request, db: Session = Depends(get_db)):
    codigos = db.query(Vehiculo.codigo).all()
    return templates.TemplateResponse("generar_codigos.html", {"request": request, "codigos": [c[0] for c in codigos]})

@app.post("/crear_codigos/generar")
def generar_codigos_pdf(codigos: str = Form(...)):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    x, y = 50, 750

    for codigo in codigos.split(","):
        codigo = codigo.strip()
        if not codigo:
            continue
        img_buffer = io.BytesIO()
        barcode.get("code128", codigo, writer=ImageWriter()).write(img_buffer)
        img_buffer.seek(0)
        c.drawImage(ImageReader(img_buffer), x, y, width=200, height=60)
        c.drawString(x, y - 15, codigo)
        y -= 100
        if y < 100:
            c.showPage()
            y = 750

    c.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment;filename=codigos.pdf"})

@app.get("/crear_codigos/generar_todos")
def generar_todos(db: Session = Depends(get_db)):
    codigos = db.query(Vehiculo.codigo).all()
    return {"todos": [c[0] for c in codigos]}

@app.post("/login")
def login(codigo: str = Form(...), db: Session = Depends(get_db_empleados)):
    emp = db.query(Empleado).filter_by(codigo=codigo).first()
    if emp:
        return {"status": "ok", "codigo": emp.codigo, "nombre": emp.nombre}
    return {"status": "error", "message": "Código no válido"}

@app.get("/obtener_empleado")
def obtener_empleado(codigo: str, db: Session = Depends(get_db_empleados)):
    emp = db.query(Empleado).filter_by(codigo=codigo).first()
    if emp:
        return {"codigo": emp.codigo, "nombre": emp.nombre}
    return JSONResponse(content={"detail": "No encontrado"}, status_code=404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
