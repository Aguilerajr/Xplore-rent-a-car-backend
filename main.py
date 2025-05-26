from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sqlite3
import os
from datetime import datetime

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "registros.db"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse("<h2>XPLORE Backend activo</h2>")

@app.get("/calidad", response_class=HTMLResponse)
def mostrar_formulario(request: Request):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT codigo FROM vehiculos")
        vehiculos = [row[0] for row in cursor.fetchall()]
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

        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                # Insertar o actualizar en clasificaciones
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
                """, (codigo, clasificacion, "Calidad", 7))

                # Agregar a la cola de lavado
                fecha_actual = datetime.now().strftime("%Y-%m-%d")
                semana_actual = datetime.now().isocalendar()[1]
                cursor.execute("""
                    INSERT INTO cola_lavado (codigo_vehiculo, clasificacion, lavador, fecha, semana, estado)
                    VALUES (?, ?, ?, ?, ?, 'en_cola')
                """, (codigo, clasificacion, None, fecha_actual, semana_actual))

                conn.commit()
                mensaje = f"✅ {codigo} clasificado y agregado a la cola de lavado"
        except Exception as e:
            mensaje = f"❌ Error: {e}"
            print(f"[ERROR] {e}")

    # Actualizar lista de vehículos
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT codigo FROM vehiculos")
        vehiculos = [row[0] for row in cursor.fetchall()]

    return templates.TemplateResponse("calidad.html", {
        "request": request,
        "vehiculos": vehiculos,
        "mensaje": mensaje
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
