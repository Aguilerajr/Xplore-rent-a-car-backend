from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import ColaLavado, Clasificacion
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/panel_cola", response_class=HTMLResponse)
def mostrar_panel_cola(request: Request, db: Session = Depends(get_db)):
    cola = db.query(
        ColaLavado,
        Clasificacion.clasificacion.label("clasificacion_detalle")
    ).join(
        Clasificacion, Clasificacion.codigo == ColaLavado.codigo_vehiculo
    ).order_by(ColaLavado.fecha).all()

    en_cola = []
    en_progreso = []

    for cl, detalle in cola:
        data = {
            "codigo_vehiculo": cl.codigo_vehiculo,
            "estado": cl.estado,
            "asignado_a": cl.asignado_a or "-",
            "fecha": cl.fecha,
            "clasificacion": detalle
        }
        if cl.estado == "en_cola":
            en_cola.append(data)
        else:
            en_progreso.append(data)

    return templates.TemplateResponse("panel_cola.html", {
        "request": request,
        "en_cola": en_cola,
        "en_progreso": en_progreso,
        "now": datetime.now()
    })

@router.get("/api/cola_lavado")
def obtener_cola_lavado(db: Session = Depends(get_db)):
    cola = db.query(
        ColaLavado,
        Clasificacion.clasificacion.label("clasificacion_detalle")
    ).join(
        Clasificacion, Clasificacion.codigo == ColaLavado.codigo_vehiculo
    ).order_by(ColaLavado.fecha).all()

    datos = []
    for cl, detalle in cola:
        datos.append({
            "codigo_vehiculo": cl.codigo_vehiculo,
            "estado": cl.estado,
            "asignado_a": cl.asignado_a or "-",
            "fecha": cl.fecha.strftime("%Y-%m-%d %H:%M:%S"),
            "clasificacion": detalle
        })

    return JSONResponse(content=datos)
