from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sqlite3
import json
import os
from datetime import datetime
from pydantic import BaseModel
import uvicorn
import re
import io
import barcode
from barcode.writer import ImageWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "registros.db"
JSON_PATH = BASE_DIR / "registros.json"

with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehiculos (
            codigo TEXT PRIMARY KEY
        );
    """)
    iniciales = [("CAR001",), ("CAR002",), ("VEH0003",), ("VEH0004",)]
    cursor.executemany("""
        INSERT OR IGNORE INTO vehiculos (codigo) VALUES (?)
    """, iniciales)
    conn.commit()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/calidad", response_class=HTMLResponse)
def mostrar_formulario(request: Request):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT codigo FROM vehiculos
            WHERE codigo NOT IN (
                SELECT codigo_vehiculo FROM cola_lavado WHERE estado = 'completado'
            )
        """)
        vehiculos = [row[0] for row in cursor.fetchall()]
    return templates.TemplateResponse("calidad.html", {
        "request": request,
        "vehiculos": vehiculos,
        "mensaje": ""
    })

@app.post("/clasificar", response_class=HTMLResponse)
def clasificar_vehiculo(request: Request, codigo: str = Form(...), suciedad: str = Form(...), tipo: str = Form(...)):
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
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clasificaciones (
                    codigo TEXT PRIMARY KEY,
                    clasificacion TEXT,
                    revisado_por TEXT,
                    tiempo_estimado INTEGER
                )
            """)
            cursor.execute("""
                INSERT OR REPLACE INTO clasificaciones (codigo, clasificacion, revisado_por, tiempo_estimado)
                VALUES (?, ?, ?, ?)
            """, (codigo, clasificacion, "Calidad", 18))
            cursor.execute("""
                INSERT OR REPLACE INTO cola_lavado (codigo_vehiculo, clasificacion, fecha, semana, estado)
                VALUES (?, ?, DATE('now'), strftime('%W', 'now'), 'en_cola')
            """, (codigo, clasificacion))
            conn.commit()
        mensaje = f"✅ {codigo} clasificado como {suciedad} - {tipo} ({clasificacion})"
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT codigo FROM vehiculos
            WHERE codigo NOT IN (
                SELECT codigo_vehiculo FROM cola_lavado WHERE estado = 'completado'
            )
        """)
        vehiculos = [row[0] for row in cursor.fetchall()]
    return templates.TemplateResponse("calidad.html", {
        "request": request,
        "vehiculos": vehiculos,
        "mensaje": mensaje
    })

class RegistroEntrada(BaseModel):
    vehiculo: str
    empleado: str

@app.post("/registrar")
def registrar_evento(entrada: RegistroEntrada):
    vehiculo = entrada.vehiculo
    empleado = entrada.empleado
    datos = cargar_datos_json()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not obtener_clasificacion(vehiculo):
        return JSONResponse(content={"status": "error", "message": f"{vehiculo} no clasificado"}, status_code=400)

    for evento in datos.get(vehiculo, []):
        if evento["empleado"] == empleado and evento["fin"] is None:
            evento["fin"] = ahora
            tiempo_inicio = datetime.strptime(evento["inicio"], "%Y-%m-%d %H:%M:%S")
            tiempo_fin = datetime.strptime(ahora, "%Y-%m-%d %H:%M:%S")
            tiempo_real = int((tiempo_fin - tiempo_inicio).total_seconds() / 60)
            tiempo_estimado = 18
            eficiencia = f"{int((tiempo_estimado / tiempo_real) * 100)}%" if tiempo_real else "N/A"
            registro_final = {
                "vehiculo": vehiculo,
                "empleado": empleado,
                "inicio": evento["inicio"],
                "fin": ahora,
                "tiempo_real": tiempo_real,
                "tiempo_estimado": tiempo_estimado,
                "eficiencia": eficiencia
            }
            agregar_registro_json(registro_final)
            guardar_datos_json(datos)
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE cola_lavado SET estado = 'completado'
                    WHERE codigo_vehiculo = ? AND estado = 'en_cola'
                """, (vehiculo,))
                conn.commit()
            return {
                "status": "checkout",
                "vehiculo": vehiculo,
                "empleado": empleado,
                "fin": ahora,
                "mensaje": f"✅ Check-out realizado y registrado en historial para {vehiculo}"
            }
    for eventos in datos.values():
        for e in eventos:
            if e["empleado"] == empleado and e["fin"] is None:
                return JSONResponse(content={"status": "error", "message": f"{empleado} ya tiene un check-in"}, status_code=400)

    if vehiculo not in datos:
        datos[vehiculo] = []
    datos[vehiculo].append({
        "empleado": empleado,
        "inicio": ahora,
        "fin": None
    })
    guardar_datos_json(datos)
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

def obtener_clasificacion(vehiculo):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT clasificacion FROM clasificaciones WHERE codigo = ?", (vehiculo,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

@app.get("/agregar_vehiculo", response_class=HTMLResponse)
def mostrar_formulario_agregar(request: Request):
    return templates.TemplateResponse("agregar_vehiculo.html", {"request": request, "mensaje": ""})

@app.post("/agregar_vehiculo", response_class=HTMLResponse)
def procesar_agregar_vehiculo(request: Request, letra: str = Form(...), digitos: str = Form(...)):
    letra = letra.upper()
    if letra not in ["P", "C", "M", "T"]:
        mensaje = "❌ Letra inválida. Debe ser P, C, M o T (mayúscula)."
    elif not re.fullmatch(r"\d{4}", digitos):
        mensaje = "❌ Los dígitos deben ser exactamente 4 números."
    else:
        codigo_vehiculo = f"{letra}-{digitos}"
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM vehiculos WHERE codigo=?", (codigo_vehiculo,))
            existe = cursor.fetchone()[0]
            if existe:
                mensaje = "❌ El código de vehículo ya existe."
            else:
                cursor.execute("INSERT INTO vehiculos (codigo) VALUES (?)", (codigo_vehiculo,))
                conn.commit()
                mensaje = f"✅ Vehículo {codigo_vehiculo} agregado correctamente."
    return templates.TemplateResponse("agregar_vehiculo.html", {
        "request": request,
        "mensaje": mensaje
    })

@app.get("/listar_vehiculos")
def listar_vehiculos():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT codigo FROM vehiculos")
        vehiculos = [row[0] for row in cursor.fetchall()]
    return {"vehiculos": vehiculos}

# Generación de códigos de barras
@app.get("/crear_codigos", response_class=HTMLResponse)
def mostrar_creador_codigos(request: Request):
    return templates.TemplateResponse("crear_codigos.html", {"request": request})

@app.post("/crear_codigos/generar")
async def generar_codigo_barras(request: Request, codigo: str = Form(...)):
    buffer = io.BytesIO()
    barcode.generate("code128", codigo, writer=ImageWriter(), output=buffer)
    buffer.seek(0)
    headers = {"Content-Disposition": f"attachment; filename={codigo}.png"}
    return StreamingResponse(buffer, media_type="image/png", headers=headers)

@app.get("/crear_codigos/generar_todos")
async def generar_todos_codigos():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT codigo FROM vehiculos")
        codigos = [row[0] for row in cursor.fetchall()]
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50
    for codigo in codigos:
        barcode_img = barcode.get("code128", codigo, writer=ImageWriter())
        barcode_buffer = io.BytesIO()
        barcode_img.write(barcode_buffer)
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
def buscar_codigos(q: str):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT codigo FROM vehiculos WHERE codigo LIKE ?", (f"{q}%",))
        resultados = [row[0] for row in cursor.fetchall()]
    return {"resultados": resultados}

