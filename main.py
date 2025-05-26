from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sqlite3
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

# Crear tabla cola_lavado con todos los campos necesarios
with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cola_lavado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_vehiculo TEXT NOT NULL,
            clasificacion TEXT NOT NULL,
            lavador TEXT,
            fecha DATE NOT NULL,
            semana INTEGER NOT NULL,
            estado TEXT DEFAULT 'en_cola',
            inicio TEXT,
            fin TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clasificaciones (
            codigo TEXT PRIMARY KEY,
            clasificacion TEXT,
            revisado_por TEXT,
            tiempo_estimado INTEGER
        );
    """)
    conn.commit()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

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
    # Leer vehículos directamente de la base de datos (en cola)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT codigo_vehiculo FROM cola_lavado WHERE estado = 'en_cola'")
    filas = cursor.fetchall()
    conn.close()

    vehiculos = [fila[0] for fila in filas]

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
        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        semana_actual = datetime.now().isocalendar()[1]

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Guardar o actualizar la clasificación
        cursor.execute("""
            INSERT OR REPLACE INTO clasificaciones (codigo, clasificacion, revisado_por, tiempo_estimado)
            VALUES (?, ?, ?, ?)
        """, (codigo, clasificacion, "Calidad", 7))

        # Insertar o actualizar en cola_lavado
        cursor.execute("""
            INSERT OR REPLACE INTO cola_lavado (codigo_vehiculo, clasificacion, lavador, fecha, semana, estado, inicio, fin)
            VALUES (?, ?, '', ?, ?, 'en_cola', '', '')
        """, (codigo, clasificacion, fecha_actual, semana_actual))
        conn.commit()
        conn.close()

        mensaje = f"✅ {codigo} clasificado como {suciedad} - {tipo} ({clasificacion})"

    # Recargar la lista desde la base de datos
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT codigo_vehiculo FROM cola_lavado WHERE estado = 'en_cola'")
    filas = cursor.fetchall()
    conn.close()

    vehiculos = [fila[0] for fila in filas]

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

    if not obtener_clasificacion(vehiculo):
        return JSONResponse(content={"status": "error", "message": f"{vehiculo} no clasificado"}, status_code=400)

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Verificar si el empleado ya está con un check-in abierto en otro vehículo
    cursor.execute("""
        SELECT codigo_vehiculo FROM cola_lavado
        WHERE lavador = ? AND estado = 'en_cola' AND inicio != '' AND fin = ''
    """, (empleado,))
    en_proceso = cursor.fetchone()
    if en_proceso:
        conn.close()
        return JSONResponse(content={"status": "error", "message": f"{empleado} ya tiene un check-in"}, status_code=400)

    # Verificar si ya tiene un check-in abierto para este vehículo
    cursor.execute("""
        SELECT inicio FROM cola_lavado
        WHERE codigo_vehiculo = ? AND lavador = ? AND estado = 'en_cola' AND inicio != '' AND fin = ''
    """, (vehiculo, empleado))
    registro = cursor.fetchone()

    if registro:
        # Si ya tiene check-in, hacer check-out
        cursor.execute("""
            UPDATE cola_lavado
            SET fin = ?, estado = 'completado'
            WHERE codigo_vehiculo = ? AND lavador = ? AND estado = 'en_cola'
        """, (ahora, vehiculo, empleado))
        conn.commit()
        conn.close()
        return {
            "status": "checkout",
            "vehiculo": vehiculo,
            "empleado": empleado,
            "fin": ahora,
            "mensaje": f"✅ Check-out realizado para {vehiculo} por {empleado}"
        }
    else:
        # Si no tiene check-in, registrarlo
        cursor.execute("""
            UPDATE cola_lavado
            SET lavador = ?, inicio = ?, fin = ''
            WHERE codigo_vehiculo = ? AND estado = 'en_cola'
        """, (empleado, ahora, vehiculo))
        conn.commit()
        conn.close()
        return {
            "status": "checkin",
            "vehiculo": vehiculo,
            "empleado": empleado,
            "inicio": ahora,
            "mensaje": f"🚗 Check-in registrado para {vehiculo} por {empleado}"
        }
