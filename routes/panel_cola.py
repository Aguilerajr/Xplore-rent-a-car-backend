from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, get_db_empleados
from models import ColaLavado, Clasificacion, Empleado
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/panel_cola", response_class=HTMLResponse)
def mostrar_panel_cola(request: Request, db: Session = Depends(get_db)):
    cola_en_cola = db.query(
        ColaLavado,
        Clasificacion.clasificacion.label("clasificacion_detalle")
    ).join(
        Clasificacion, Clasificacion.codigo == ColaLavado.codigo_vehiculo
    ).filter(ColaLavado.estado == "en_cola").order_by(ColaLavado.fecha).all()

    cola_en_proceso = db.query(
        ColaLavado,
        Clasificacion.clasificacion.label("clasificacion_detalle")
    ).join(
        Clasificacion, Clasificacion.codigo == ColaLavado.codigo_vehiculo
    ).filter(ColaLavado.estado == "en_proceso").order_by(ColaLavado.fecha).all()

    def formatear(cola):
        return [{
            "codigo_vehiculo": cl.codigo_vehiculo,
            "estado": cl.estado,
            "asignado_a": cl.asignado_a,
            "fecha": cl.fecha,
            "clasificacion": detalle
        } for cl, detalle in cola]

    return templates.TemplateResponse("panel_cola.html", {
        "request": request,
        "cola_en_cola": formatear(cola_en_cola),
        "cola_en_proceso": formatear(cola_en_proceso),
        "now": datetime.now()
    })


@router.get("/api/cola_lavado")
def obtener_cola_lavado(
    db: Session = Depends(get_db),
    db_emp: Session = Depends(get_db_empleados)
):
    def obtener_nombres(asignados_raw: str) -> list:
        if not asignados_raw:
            return []
        codigos = [c.strip() for c in asignados_raw.split(",") if c.strip()]
        nombres = []
        for cod in codigos:
            emp = db_emp.query(Empleado).filter_by(codigo=cod).first()
            if emp and emp.nombre:
                nombres.append(f"{cod} - {emp.nombre}")
            else:
                nombres.append(cod)
        return nombres

    cola_en_cola = db.query(
        ColaLavado,
        Clasificacion.clasificacion.label("clasificacion_detalle")
    ).join(
        Clasificacion, Clasificacion.codigo == ColaLavado.codigo_vehiculo
    ).filter(ColaLavado.estado == "en_cola").order_by(ColaLavado.fecha).all()

    cola_en_proceso = db.query(
        ColaLavado,
        Clasificacion.clasificacion.label("clasificacion_detalle")
    ).join(
        Clasificacion, Clasificacion.codigo == ColaLavado.codigo_vehiculo
    ).filter(ColaLavado.estado == "en_proceso").order_by(ColaLavado.fecha).all()

    def serializar(cola):
        return [{
            "codigo_vehiculo": cl.codigo_vehiculo,
            "estado": cl.estado,
            "asignado_a": obtener_nombres(cl.asignado_a),
            "fecha": cl.fecha.strftime("%Y-%m-%d %H:%M:%S"),
            "clasificacion": detalle
        } for cl, detalle in cola]

    return JSONResponse(content={
        "en_cola": serializar(cola_en_cola),
        "en_proceso": serializar(cola_en_proceso)
    })
