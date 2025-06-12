from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, get_db_empleados
from models import ColaLavado, Empleado, Clasificacion

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/asignar", response_class=HTMLResponse)
def mostrar_asignacion(request: Request, db: Session = Depends(get_db)):
    vehiculos_en_cola = db.query(ColaLavado.codigo_vehiculo).filter(
        ColaLavado.estado.in_(["en_cola", "en_proceso"])
    ).all()
    disponibles = [v[0] for v in vehiculos_en_cola]

    return templates.TemplateResponse("asignar.html", {
        "request": request,
        "vehiculos": disponibles,
        "mensaje": ""
    })

@router.post("/asignar", response_class=HTMLResponse)
def asignar_vehiculo(
    request: Request,
    vehiculo: str = Form(...),
    empleado: str = Form(...),
    db: Session = Depends(get_db),
    db_emp: Session = Depends(get_db_empleados)
):
    vehiculo_obj = db.query(ColaLavado).filter(
        ColaLavado.codigo_vehiculo == vehiculo,
        ColaLavado.estado.in_(["en_cola", "en_proceso"])
    ).first()
    empleado_obj = db_emp.query(Empleado).filter_by(codigo=empleado).first()
    clasificacion = db.query(Clasificacion).filter_by(codigo=vehiculo).first()

    if not vehiculo_obj:
        mensaje = f"❌ El vehículo {vehiculo} no está en cola ni en proceso."
    elif not empleado_obj:
        mensaje = f"❌ El empleado {empleado} no existe."
    elif not clasificacion:
        mensaje = f"❌ El vehículo {vehiculo} no ha sido clasificado."
    else:
        # Solo actualizar a en_proceso si estaba en cola
        if vehiculo_obj.estado == "en_cola":
            vehiculo_obj.estado = "en_proceso"
            db.commit()
        mensaje = f"✅ Vehículo {vehiculo} fue asignado al empleado {empleado_obj.nombre}."

    vehiculos_en_cola = db.query(ColaLavado.codigo_vehiculo).filter(
        ColaLavado.estado.in_(["en_cola", "en_proceso"])
    ).all()
    disponibles = [v[0] for v in vehiculos_en_cola]

    return templates.TemplateResponse("asignar.html", {
        "request": request,
        "vehiculos": disponibles,
        "mensaje": mensaje
    })
