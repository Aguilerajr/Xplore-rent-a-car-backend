from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sqlite3
import json
import os
from datetime import datetime
from pydantic import BaseModel
import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "registros.db"
JSON_PATH = BASE_DIR / "registros.json"

# Crear tabla cola_lavado si no existe
with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cola_lavado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_vehiculo TEXT UNIQUE NOT NULL,
            clasificacion TEXT NOT NULL,
            lavador TEXT,
            fecha DATE NOT NULL,
            semana INTEGER NOT NULL,
            estado TEXT DEFAULT 'en_cola'
        );
    """)
    conn.commit()

# Crear tabla clasificaciones si no existe
with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clasificaciones (
            codigo TEXT PRIMARY KEY,
            clasificacion TEXT,
            revisado_por TEXT,
            tiempo_estimado INTEGER
        );
    """)
    conn.commit()

# Crear tabla vehiculos si no existe (con algunos códigos de ejemplo)
with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehiculos (
            codigo TEXT PRIMARY KEY
        );
    """)
    # Insertar algunos vehículos de prueba si no existen
    cursor.executemany("""
        INSERT OR IGNORE INTO vehiculos (codigo) VALUES (?)
    """, [('CAR001',), ('CAR002',), ('VEH0003',), ('VEH0004',)])
    conn.commit()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

def cargar_datos_json():
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_datos_json(data):
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def obtener_clasificacion(vehiculo):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT clasificacion FROM clasificaciones WHERE codigo = ?", (vehiculo,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse("<h2>XPLORE Backend activo</h2>")

@app.get("/calidad", response_class=HTMLResponse)
def mostrar_formulario(request: Request):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT codigo FROM vehiculos")
    vehiculos = [row[0] for row in cursor.fetchall()]
    conn.close()
    return templates.TemplateResponse("calidad.html", {
        "request": request,
        "vehiculos": vehiculos,
        "mensaje": ""
    })

@app.post("/clasificar", response_class=HTMLResponse)
def clasificar_vehiculo(
    request: Request,
    codigo: str = Form(...),
    suciedad: str = Form(...),
    tipo: str = Form(...)
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

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO clasificaciones (codigo, clasificacion, revisado_por, tiempo_estimado)
            VALUES (?, ?, ?, ?)
        """, (codigo, clasificacion, "Calidad", 7))

        # Insertar o actualizar la cola de lavado
        cursor.execute("""
            INSERT INTO cola_lavado (codigo_vehiculo, clasificacion, fecha, semana, estado)
            VALUES (?, ?, DATE('now'), strftime('%W', 'now'), 'en_cola')
            ON CONFLICT(codigo_vehiculo) DO UPDATE SET
                clasificacion=excluded.clasificacion,
                estado='en_cola'
        """, (codigo, clasificacion))
        conn.commit()
        conn.close()

        mensaje = f"✅ {codigo} clasificado como {suciedad} - {tipo} ({clasificacion})"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT codigo FROM vehiculos")
    vehiculos = [row[0] for row in cursor.fetchall()]
    conn.close()

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
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not obtener_clasificacion(vehiculo):
        return JSONResponse(content={"status": "error", "message": f"{vehiculo} no clasificado"}, status_code=400)

    datos = cargar_datos_json()
    eventos_vehiculo = datos.get(vehiculo, [])

    # Checkout
    for evento in eventos_vehiculo:
        if evento["empleado"] == empleado and evento["fin"] is None:
            evento["fin"] = ahora
            guardar_datos_json(datos)

            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE cola_lavado
                    SET estado = 'completado'
                    WHERE codigo_vehiculo = ? AND estado != 'completado'
                """, (vehiculo,))
                conn.commit()

            return {
                "status": "checkout",
                "vehiculo": vehiculo,
                "empleado": empleado,
                "fin": ahora,
                "mensaje": f"✅ Check-out completado para {vehiculo} por {empleado}"
            }

    # Verificar si este empleado tiene otro check-in abierto
    for eventos in datos.values():
        for e in eventos:
            if e["empleado"] == empleado and e["fin"] is None:
                return JSONResponse(content={"status": "error", "message": f"{empleado} ya tiene un check-in abierto"}, status_code=400)

    # Check-in nuevo
    nuevo_evento = {"empleado": empleado, "inicio": ahora, "fin": None}
    if vehiculo not in datos:
        datos[vehiculo] = []
    datos[vehiculo].append(nuevo_evento)
    guardar_datos_json(datos)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cola_lavado (codigo_vehiculo, clasificacion, fecha, semana, estado, lavador)
            SELECT ?, clasificacion, DATE('now'), strftime('%W', 'now'), 'en_cola', ?
            FROM clasificaciones WHERE codigo = ?
            ON CONFLICT (codigo_vehiculo) DO UPDATE SET estado='en_cola'
        """, (vehiculo, empleado, vehiculo))
        conn.commit()

    return {
        "status": "checkin",
        "vehiculo": vehiculo,
        "empleado": empleado,
        "inicio": ahora,
        "mensaje": f"🚗 Check-in registrado para {vehiculo} por {empleado}"
    }
