from fastapi import FastAPI, Form, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os
import json
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

# Configuración PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:bgNLRBzPghPvzlMkAROLGTIrNlBcaVgt@crossover.proxy.rlwy.net:11506/railway")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Definición de modelos
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

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

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
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
JSON_PATH = BASE_DIR / "registros.json"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

def get_db():
    db = SessionLocal()
    try:
        yield db
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
    return templates.TemplateResponse("calidad.html", {
        "request": request,
        "vehiculos": disponibles,
        "mensaje": ""
    })

@app.post("/clasificar", response_class=HTMLResponse)
def clasificar_vehiculo(
    request: Request,
    codigo: str = Form(...),
    suciedad: str = Form(...),
    tipo: str = Form(...),
    db: Session = Depends(get_db)
):
    clasificacion_map = {
        "Muy sucio": "1",
        "Normal": "2",
        "Poco sucio": "3",
        "Shampuseado": "4",
        "Franeleado": "5"
    }
    tipo_map = {
        "Camioneta Grande": "A",
        "Camioneta pequeña": "B",
        "Busito": "C",
        "Pick Up": "D",
        "Turismo normal": "E",
        "Turismo pequeño": "F"
    }

    grado = clasificacion_map.get(suciedad)
    tipo_vehiculo = tipo_map.get(tipo)

    if not grado or not tipo_vehiculo:
        mensaje = "❌ Clasificación inválida"
    else:
        clasificacion = tipo_vehiculo + grado
        # Eliminar si ya existe
        db.query(Clasificacion).filter(Clasificacion.codigo == codigo).delete()
        db.add(Clasificacion(
            codigo=codigo,
            clasificacion=clasificacion,
            revisado_por="Calidad",
            tiempo_estimado=18
        ))
        # Eliminar cola anterior completada
        db.query(ColaLavado).filter(
            ColaLavado.codigo_vehiculo == codigo,
            ColaLavado.estado == "completado"
        ).delete()
        db.add(ColaLavado(
            codigo_vehiculo=codigo,
            clasificacion=clasificacion,
            fecha=datetime.utcnow(),
            semana=datetime.utcnow().isocalendar()[1],
            estado="en_cola"
        ))
        db.commit()
        mensaje = f"✅ {codigo} clasificado como {suciedad} - {tipo} ({clasificacion})"
    
    vehiculos = db.query(Vehiculo.codigo).all()
    codigos = [v[0] for v in vehiculos]
    completados = db.query(ColaLavado.codigo_vehiculo).filter(ColaLavado.estado == "completado").all()
    completados_set = {c[0] for c in completados}
    disponibles = [cod for cod in codigos if cod not in completados_set]

    return templates.TemplateResponse("calidad.html", {
        "request": request,
        "vehiculos": disponibles,
        "mensaje": mensaje
    })


class RegistroEntrada(BaseModel):
    vehiculo: str
    empleado: str


@app.post("/registrar")
def registrar_evento(entrada: RegistroEntrada, db: Session = Depends(get_db)):
    vehiculo = entrada.vehiculo
    empleado = entrada.empleado
    datos = cargar_datos_json()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    clasif = db.query(Clasificacion.clasificacion).filter(Clasificacion.codigo == vehiculo).first()
    if not clasif:
        return JSONResponse(content={"status": "error", "message": f"{vehiculo} no clasificado"}, status_code=400)

    # Buscar si ya hay un evento abierto para este empleado en otro vehículo
    registro_abierto_otro = db.query(RegistroLavado).filter(
        RegistroLavado.empleado == empleado,
        RegistroLavado.fin.is_(None),
        RegistroLavado.vehiculo != vehiculo
    ).first()
    if registro_abierto_otro:
        return JSONResponse(
            content={"status": "error", "message": f"{empleado} ya tiene un check-in en otro vehículo"},
            status_code=400
        )

    # Buscar si ya hay un evento abierto para este vehículo y empleado
    registro_abierto = db.query(RegistroLavado).filter(
        RegistroLavado.vehiculo == vehiculo,
        RegistroLavado.empleado == empleado,
        RegistroLavado.fin.is_(None)
    ).first()

    if registro_abierto:
        registro_abierto.fin = ahora
        tiempo_inicio = datetime.strptime(registro_abierto.inicio.strftime("%Y-%m-%d %H:%M:%S"), "%Y-%m-%d %H:%M:%S")
        tiempo_fin = datetime.strptime(ahora, "%Y-%m-%d %H:%M:%S")
        tiempo_real = int((tiempo_fin - tiempo_inicio).total_seconds() / 60)
        tiempo_estimado = 18
        eficiencia = f"{int((tiempo_estimado / tiempo_real) * 100)}%" if tiempo_real else "N/A"
        registro_abierto.tiempo_real = tiempo_real
        registro_abierto.tiempo_estimado = tiempo_estimado
        registro_abierto.eficiencia = eficiencia
        db.commit()

        # Verificar si hay otros empleados trabajando en este vehículo
        otros_trabajando = db.query(RegistroLavado).filter(
            RegistroLavado.vehiculo == vehiculo,
            RegistroLavado.fin.is_(None),
            RegistroLavado.id != registro_abierto.id
        ).first()

        if not otros_trabajando:
            # No hay más empleados trabajando → eliminar de cola y clasificaciones
            db.query(ColaLavado).filter(
                ColaLavado.codigo_vehiculo == vehiculo,
                ColaLavado.estado == "en_cola"
            ).delete()
            db.query(Clasificacion).filter(Clasificacion.codigo == vehiculo).delete()
            db.commit()

        return {
            "status": "checkout",
            "vehiculo": vehiculo,
            "empleado": empleado,
            "fin": ahora,
            "mensaje": f"✅ Check-out realizado y registrado en historial para {vehiculo}"
        }

    # Registrar nuevo check-in
    nuevo_registro = RegistroLavado(
        vehiculo=vehiculo,
        empleado=empleado,
        inicio=datetime.now()
    )
    db.add(nuevo_registro)
    db.commit()

    return {
        "status": "checkin",
        "vehiculo": vehiculo,
        "empleado": empleado,
        "inicio": ahora,
        "mensaje": f"🚗 Check-in registrado para {vehiculo} por {empleado}"
    }


def cargar_datos_json():
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_datos_json(data):
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def agregar_registro_json(registro):
    data = cargar_datos_json()
    if "registros" not in data:
        data["registros"] = []
    data["registros"].append(registro)
    guardar_datos_json(data)


@app.get("/agregar_vehiculo", response_class=HTMLResponse)
def mostrar_formulario_agregar(request: Request):
    return templates.TemplateResponse("agregar_vehiculo.html", {"request": request, "mensaje": ""})


@app.post("/agregar_vehiculo", response_class=HTMLResponse)
def procesar_agregar_vehiculo(
    request: Request,
    letra: str = Form(...),
    digitos: str = Form(...),
    db: Session = Depends(get_db)
):
    letra = letra.upper()
    if letra not in ["P", "C", "M", "T"]:
        mensaje = "❌ Letra inválida. Debe ser P, C, M o T (mayúscula)."
    elif not re.fullmatch(r"\d{4}", digitos):
        mensaje = "❌ Los dígitos deben ser exactamente 4 números."
    else:
        codigo_vehiculo = f"{letra}-{digitos}"
        if db.query(Vehiculo).filter_by(codigo=codigo_vehiculo).first():
            mensaje = "❌ El código de vehículo ya existe."
        else:
            db.add(Vehiculo(codigo=codigo_vehiculo))
            db.commit()
            mensaje = f"✅ Vehículo {codigo_vehiculo} agregado correctamente."

    return templates.TemplateResponse("agregar_vehiculo.html", {
        "request": request,
        "mensaje": mensaje
    })


@app.get("/listar_vehiculos")
def listar_vehiculos(db: Session = Depends(get_db)):
    vehiculos = db.query(Vehiculo.codigo).all()
    return {"vehiculos": [v[0] for v in vehiculos]}


# Generación de códigos de barras
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
    codigos = [v.codigo for v in db.query(Vehiculo.codigo).all()]
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


@app.get("/buscar_codigos")
def buscar_codigos(q: str, db: Session = Depends(get_db)):
    resultados = db.query(Vehiculo.codigo).filter(Vehiculo.codigo.like(f"{q}%")).all()
    return {"resultados": [r[0] for r in resultados]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)