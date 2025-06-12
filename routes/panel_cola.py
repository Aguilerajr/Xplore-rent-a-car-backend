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
    # Traer cola con descripción desde la tabla clasificaciones
    cola = db.query(
        ColaLavado,
        Clasificacion.clasificacion.label("clasificacion_detalle")
    ).join(
        Clasificacion, Clasificacion.codigo == ColaLavado.codigo_vehiculo
    ).order_by(ColaLavado.fecha).all()

    # Preparar datos combinados para la plantilla
    cola_formateada = []
    for cl, detalle in cola:
        cola_formateada.append({
            "codigo_vehiculo": cl.codigo_vehiculo,
            "estado": cl.estado,
            "asignado_a": cl.asignado_a,
            "fecha": cl.fecha,
            "clasificacion": detalle  # ejemplo: "D2"
        })

    return templates.TemplateResponse("panel_cola.html", {
        "request": request,
        "cola_lavado": cola_formateada,
        "now": datetime.now()
    })


# NUEVA RUTA API para recarga automática desde el frontend
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
