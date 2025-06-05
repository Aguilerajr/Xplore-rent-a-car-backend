from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import Vehiculo, Clasificacion, ColaLavado
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")

TIEMPOS_ESTIMADOS = {
    "A1": 120, "A2": 60, "A3": 30, "A4": 240, "A5": 7,
    "B1": 100, "B2": 50, "B3": 25, "B4": 240, "B5": 7,
    "C1": 100, "C2": 60, "C3": 30, "C4": 240, "C5": 7,
    "D1": 120, "D2": 60, "D3": 30, "D4": 240, "D5": 7,
    "E1": 90,  "E2": 60, "E3": 40, "E4": 240, "E5": 7,
    "F1": 50,  "F2": 35, "F3": 20, "F4": 240, "F5": 7
}

@router.get("/calidad", response_class=HTMLResponse)
def mostrar_formulario(request: Request, db: Session = Depends(get_db)):
    vehiculos = db.query(Vehiculo.codigo).all()
    codigos = [v[0] for v in vehiculos]
    completados = db.query(ColaLavado.codigo_vehiculo).filter(ColaLavado.estado == "completado").all()
    disponibles = [c for c in codigos if c not in {x[0] for x in completados}]
    return templates.TemplateResponse("calidad.html", {
        "request": request,
        "vehiculos": disponibles,
        "mensaje": ""
    })

@router.post("/clasificar", response_class=HTMLResponse)
def clasificar_vehiculo(
    request: Request,
    codigo: str = Form(...),
    suciedad: str = Form(...),
    tipo: str = Form(...),
    db: Session = Depends(get_db)
):
    clasificacion_map = {"Muy sucio": "1", "Normal": "2", "Poco sucio": "3", "Shampuseado": "4", "Franeleado": "5"}
    tipo_map = {
        "Camioneta Grande": "A", "Camioneta pequeña": "B", "Busito": "C",
        "Pick Up": "D", "Turismo normal": "E", "Turismo pequeño": "F"
    }

    grado = clasificacion_map.get(suciedad)
    tipo_vehiculo = tipo_map.get(tipo)

    if not grado or not tipo_vehiculo:
        mensaje = "❌ Clasificación inválida"
    else:
        clasificacion = tipo_vehiculo + grado
        tiempo_estimado = TIEMPOS_ESTIMADOS.get(clasificacion, 18)

        db.query(Clasificacion).filter(Clasificacion.codigo == codigo).delete()

        db.add(Clasificacion(
            codigo=codigo,
            clasificacion=clasificacion,
            revisado_por="Calidad",
            tiempo_estimado=tiempo_estimado
        ))

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
    disponibles = [c for c in codigos if c not in {x[0] for x in completados}]

    return templates.TemplateResponse("calidad.html", {
        "request": request,
        "vehiculos": disponibles,
        "mensaje": mensaje
    })

@router.get("/buscar_codigos")
def buscar_codigos(q: str = "", db: Session = Depends(get_db)):
    codigos = db.query(Vehiculo.codigo).filter(Vehiculo.codigo.ilike(f"%{q}%")).all()
    return {"resultados": [c[0] for c in codigos]}
