from fastapi import FastAPI, Form, Request, HTTPException
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
import re

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "registros.db"
JSON_PATH = BASE_DIR / "registros.json"

# Crear tabla vehiculos si no existe
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
def home():
    return HTMLResponse("<h2>XPLORE Backend activo</h2>")

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

