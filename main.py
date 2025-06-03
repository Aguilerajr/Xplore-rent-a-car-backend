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

# BASE DE DATOS VEHÍCULOS
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:bgNLRBzPghPvzlMkAROLGTIrNlBcaVgt@crossover.proxy.rlwy.net:11506/railway")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# BASE DE DATOS EMPLEADOS
DATABASE_URL_EMPLEADOS = "postgresql://postgres:gFQOssQuCNFeLZqvKBNcERsRrxWEiZlJ@shuttle.proxy.rlwy.net:42664/railway"
engine_empleados = create_engine(DATABASE_URL_EMPLEADOS)
SessionEmpleados = sessionmaker(autocommit=False, autoflush=False, bind=engine_empleados)
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
    completados_set = {c[0] for c in completados}
    disponibles = [cod for cod in codigos if cod not in completados_set]
    db.close()
    return templates.TemplateResponse("calidad.html", {"request": request, "vehiculos": disponibles, "mensaje": ""})

@app.post("/clasificar", response_class=HTMLResponse)
def clasificar_vehiculo(
    request: Request,
    codigo: str = Form(...),
    suciedad: str = Form(...),
    tipo: str = Form(...),
    db: Session = Depends(get_db)
):
    clasificacion_map = {
        "Muy sucio": "1", "Normal": "2", "Poco sucio": "3", "Shampuseado": "4", "Franeleado": "5"
    }
    tipo_map = {
        "Camioneta Grande": "A", "Camioneta pequeña": "B", "Busito": "C", "Pick Up": "D",
        "Turismo normal": "E", "Turismo pequeño": "F"
    }

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

@app.get("/buscar_codigos")
def buscar_codigos(q: str, db: Session = Depends(get_db)):
    resultados = db.query(Vehiculo.codigo).filter(Vehiculo.codigo.like(f"{q}%")).all()
    return {"resultados": [r[0] for r in resultados]}

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

@app.get("/crear_codigos", response_class=HTMLResponse)
def mostrar_creador_codigos(request: Request):
    return templates.TemplateResponse("crear_codigos.html", {"request": request})

@app.post("/crear_codigos/generar")
async def generar_codigo_barras(request: Request, codigo: str = Form(...)):
    buffer = io.BytesIO()
    code128_class = barcode.get_barcode_class("code128")
    code128_instance = code128_class(codigo, writer=ImageWriter())
    code128_instance.write(buffer)
    buffer.seek(0)
    headers = {"Content-Disposition": f"attachment; filename={codigo}.png"}
    return StreamingResponse(buffer, media_type="image/png", headers=headers)

@app.get("/crear_codigos/generar_todos")
async def generar_todos_codigos(db: Session = Depends(get_db)):
    codigos = [v.codigo for v in db.query(Vehiculo).all()]
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50
    code128_class = barcode.get_barcode_class("code128")

    for codigo in codigos:
        barcode_buffer = io.BytesIO()
        code128_class(codigo, writer=ImageWriter()).write(barcode_buffer)
        barcode_buffer.seek(0)
        c.drawImage(ImageReader(barcode_buffer), 50, y - 50, width=300, height=50)
        c.drawString(50, y - 60, codigo)
        y -= 100
        if y < 100:
            c.showPage()
            y = height - 50
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
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
