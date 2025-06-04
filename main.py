from fastapi import FastAPI, Form, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from contextlib import asynccontextmanager
from datetime import datetime
import barcode
from barcode.writer import ImageWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import io, os, re

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:bgNLRBzPghPvzlMkAROLGTIrNlBcaVgt@crossover.proxy.rlwy.net:11506/railway")
DATABASE_URL_EMPLEADOS = "postgresql://postgres:gFQOssQuCNFeLZqvKBNcERsRrxWEiZlJ@shuttle.proxy.rlwy.net:42664/railway"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

engine_empleados = create_engine(DATABASE_URL_EMPLEADOS)
SessionEmpleados = sessionmaker(autocommit=False, autoflush=False, bind=engine_empleados)
BaseEmpleados = declarative_base()

TIEMPOS_ESTIMADOS = {
    "A1": 120, "A2": 60, "A3": 30, "A4": 240, "A5": 7,
    "B1": 100, "B2": 50, "B3": 25, "B4": 240, "B5": 7,
    "C1": 100, "C2": 60, "C3": 30, "C4": 240, "C5": 7,
    "D1": 120, "D2": 60, "D3": 30, "D4": 240, "D5": 7,
    "E1": 90,  "E2": 60, "E3": 40, "E4": 240, "E5": 7,
    "F1": 50,  "F2": 35, "F3": 20, "F4": 240, "F5": 7
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
    nombre_empleado = Column(String)
    inicio = Column(DateTime)
    fin = Column(DateTime, nullable=True)
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
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def get_db(): yield (db := SessionLocal()); db.close()
def get_db_empleados(): yield (db := SessionEmpleados()); db.close()

def init_db():
    db = SessionLocal()
    for cod in ["CAR001", "CAR002", "VEH0003", "VEH0004"]:
        if not db.query(Vehiculo).filter_by(codigo=cod).first():
            db.add(Vehiculo(codigo=cod))
    db.commit()
    db.close()

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/calidad", response_class=HTMLResponse)
def mostrar_formulario(request: Request):
    db = SessionLocal()
    todos = db.query(Vehiculo.codigo).all()
    completados = db.query(ColaLavado.codigo_vehiculo).filter(ColaLavado.estado == "completado").all()
    disponibles = [v[0] for v in todos if v[0] not in {x[0] for x in completados}]
    db.close()
    return templates.TemplateResponse("calidad.html", {"request": request, "vehiculos": disponibles, "mensaje": ""})

@app.post("/clasificar", response_class=HTMLResponse)
def clasificar_vehiculo(request: Request, codigo: str = Form(...), suciedad: str = Form(...), tipo: str = Form(...), db: Session = Depends(get_db)):
    clasificacion_map = {"Muy sucio": "1", "Normal": "2", "Poco sucio": "3", "Shampuseado": "4", "Franeleado": "5"}
    tipo_map = {"Camioneta Grande": "A", "Camioneta pequeña": "B", "Busito": "C", "Pick Up": "D", "Turismo normal": "E", "Turismo pequeño": "F"}
    grado, tipo_vehiculo = clasificacion_map.get(suciedad), tipo_map.get(tipo)
    if not grado or not tipo_vehiculo:
        mensaje = "❌ Clasificación inválida"
    else:
        clasificacion = tipo_vehiculo + grado
        tiempo_estimado = TIEMPOS_ESTIMADOS.get(clasificacion, 18)
        db.query(Clasificacion).filter_by(codigo=codigo).delete()
        db.add(Clasificacion(codigo=codigo, clasificacion=clasificacion, revisado_por="Calidad", tiempo_estimado=tiempo_estimado))
        db.query(ColaLavado).filter_by(codigo_vehiculo=codigo, estado="completado").delete()
        db.add(ColaLavado(codigo_vehiculo=codigo, clasificacion=clasificacion, semana=datetime.utcnow().isocalendar()[1], estado="en_cola"))
        db.commit()
        mensaje = f"✅ {codigo} clasificado como {suciedad} - {tipo} ({clasificacion})"
    return templates.TemplateResponse("calidad.html", {"request": request, "vehiculos": codigo, "mensaje": mensaje})

@app.post("/checkin")
def checkin(codigo: str = Form(...), empleado: str = Form(...), db: Session = Depends(get_db), db_emp: Session = Depends(get_db_empleados)):
    activo = db.query(RegistroLavado).filter_by(empleado=empleado, fin=None).first()
    if activo:
        return {"error": "Ya tienes un check-in activo"}

    clasificacion = db.query(Clasificacion).filter_by(codigo=codigo).first()
    en_cola = db.query(ColaLavado).filter_by(codigo_vehiculo=codigo, estado="en_cola").first()
    if not clasificacion or not en_cola:
        return {"error": "Vehículo no disponible"}

    emp = db_emp.query(Empleado).filter_by(codigo=empleado).first()
    nombre = emp.nombre if emp else "Desconocido"
    nuevo = RegistroLavado(
        vehiculo=codigo, empleado=empleado, nombre_empleado=nombre,
        inicio=datetime.utcnow(), fin=None,
        tiempo_real=0, tiempo_estimado=clasificacion.tiempo_estimado,
        eficiencia="0%"
    )
    db.add(nuevo)
    db.commit()
    return {"status": "checkin exitoso"}

@app.post("/registrar")
def registrar_lavado(codigo: str = Form(...), empleado: str = Form(...), inicio: str = Form(...), fin: str = Form(...), db: Session = Depends(get_db)):
    inicio_dt, fin_dt = datetime.fromisoformat(inicio), datetime.fromisoformat(fin)
    tiempo_real = int((fin_dt - inicio_dt).total_seconds() / 60)

    clasificacion = db.query(Clasificacion).filter_by(codigo=codigo).first()
    if not clasificacion:
        return {"error": "No clasificado"}

    eficiencia = round((clasificacion.tiempo_estimado / tiempo_real) * 100, 1) if tiempo_real > 0 else 0
    emp = SessionEmpleados().query(Empleado).filter_by(codigo=empleado).first()
    nombre = emp.nombre if emp else "Desconocido"

    registro = db.query(RegistroLavado).filter_by(vehiculo=codigo, empleado=empleado, fin=None).first()
    if registro:
        registro.fin = fin_dt
        registro.tiempo_real = tiempo_real
        registro.eficiencia = f"{eficiencia}%"
    else:
        return {"error": "No hay check-in previo"}

    db.query(ColaLavado).filter_by(codigo_vehiculo=codigo).update({"estado": "completado"})

    activos = db.query(RegistroLavado).filter_by(vehiculo=codigo, fin=None).count()
    if activos == 0:
        db.query(ColaLavado).filter_by(codigo_vehiculo=codigo).delete()
        db.query(Clasificacion).filter_by(codigo=codigo).delete()

    db.commit()
    return {"status": "ok", "eficiencia": eficiencia}

@app.get("/buscar_codigos")
def buscar_codigos(q: str, db: Session = Depends(get_db)):
    resultados = db.query(Vehiculo.codigo).filter(Vehiculo.codigo.like(f"{q}%")).all()
    return {"resultados": [r[0] for r in resultados]}

@app.post("/crear_codigos/generar")
def generar_codigos_pdf_o_png(codigos: str = Form(...)):
    codigos_list = [c.strip() for c in codigos.split(",") if c.strip()]
    if not codigos_list:
        return JSONResponse(content={"error": "No se ingresaron códigos válidos."}, status_code=400)
    if len(codigos_list) == 1:
        buffer = io.BytesIO()
        barcode.get("code128", codigos_list[0], writer=ImageWriter()).write(buffer)
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="image/png", headers={"Content-Disposition": f"inline; filename={codigos_list[0]}.png"})

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    x, y = 50, 750
    for codigo in codigos_list:
        img_buf = io.BytesIO()
        barcode.get("code128", codigo, writer=ImageWriter()).write(img_buf)
        img_buf.seek(0)
        c.drawImage(ImageReader(img_buf), x, y, width=200, height=60)
        c.drawString(x, y - 15, codigo)
        y -= 100
        if y < 100: c.showPage(); y = 750
    c.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=codigos.pdf"})

@app.post("/login")
def login(codigo: str = Form(...), db: Session = Depends(get_db_empleados)):
    empleado = db.query(Empleado).filter_by(codigo=codigo).first()
    if empleado:
        return {"status": "ok", "codigo": empleado.codigo, "nombre": empleado.nombre}
    return {"status": "error", "message": "Código no válido"}

@app.get("/verificar_disponibilidad")
def verificar_disponibilidad(codigo: str, db: Session = Depends(get_db)):
    clasificacion = db.query(Clasificacion).filter_by(codigo=codigo).first()
    en_cola = db.query(ColaLavado).filter_by(codigo_vehiculo=codigo, estado="en_cola").first()
    return {"disponible": bool(clasificacion and en_cola)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
