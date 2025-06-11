from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, get_db_empleados
from models import ColaLavado, Empleado, Clasificacion, RegistroLavado
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/asignar", response_class=HTMLResponse)
def mostrar_asignacion(request: Request, db: Session = Depends(get_db), db_emp: Session = Depends(get_db_empleados)):
    # Mostrar todos los vehículos en cola o en progreso
    vehiculos_en_cola = db.query(ColaLavado.codigo_vehiculo).filter(
        ColaLavado.estado.in_(["en_cola", "en_progreso"])
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
    vehiculo_en_cola = db.query(ColaLavado).filter(
        ColaLavado.codigo_vehiculo == vehiculo,
        ColaLavado.estado.in_(["en_cola", "en_progreso"])
    ).first()

    empleado_obj = db_emp.query(Empleado).filter_by(codigo=empleado).first()
    clasificacion = db.query(Clasificacion).filter_by(codigo=vehiculo).first()

    if not vehiculo_en_cola:
        mensaje = f"❌ El vehículo {vehiculo} no está en cola ni en progreso."
    elif not empleado_obj:
        mensaje = f"❌ El empleado {empleado} no existe."
    elif not clasificacion:
        mensaje = f"❌ El vehículo {vehiculo} no ha sido clasificado."
    else:
        # Verificar si ya tiene un check-in abierto en este vehículo
        existe = db.query(RegistroLavado).filter_by(
            vehiculo=vehiculo,
            empleado=empleado,
            fin=None
        ).first()

        if existe:
            mensaje = f"⚠️ El empleado {empleado} ya está asignado a {vehiculo}."
        else:
            nuevo_registro = RegistroLavado(
                vehiculo=vehiculo,
                empleado=empleado,
                nombre_empleado=empleado_obj.nombre,
                inicio=datetime.now(),
                fin=None,
                tiempo_real=0,
                tiempo_estimado=clasificacion.tiempo_estimado,
                eficiencia="0%"
            )
            db.add(nuevo_registro)
            vehiculo_en_cola.estado = "en_progreso"
            db.commit()
            mensaje = f"✅ Vehículo {vehiculo} asignado a empleado {empleado}."

    # Volver a cargar los vehículos válidos
    vehiculos_en_cola = db.query(ColaLavado.codigo_vehiculo).filter(
        ColaLavado.estado.in_(["en_cola", "en_progreso"])
    ).all()
    disponibles = [v[0] for v in vehiculos_en_cola]

    return templates.TemplateResponse("asignar.html", {
        "request": request,
        "vehiculos": disponibles,
        "mensaje": mensaje
    })
