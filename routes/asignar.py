from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, get_db_empleados
from models import ColaLavado, Empleado

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/asignar", response_class=HTMLResponse)
def mostrar_asignacion(request: Request, db: Session = Depends(get_db), db_emp: Session = Depends(get_db_empleados)):
    vehiculos = db.query(ColaLavado.codigo_vehiculo).filter_by(estado="en_cola").all()
    empleados = db_emp.query(Empleado.codigo).all()
    return templates.TemplateResponse("asignar.html", {
        "request": request,
        "vehiculos": [v[0] for v in vehiculos],
        "empleados": [e[0] for e in empleados],
        "mensaje": ""
    })

@router.post("/asignar", response_class=HTMLResponse)
def asignar_vehiculo(
    request: Request,
    codigo_vehiculo: str = Form(...),
    codigo_empleado: str = Form(...),
    db: Session = Depends(get_db),
    db_emp: Session = Depends(get_db_empleados)
):
    # Validaciones opcionales aquí
    vehiculo = db.query(ColaLavado).filter_by(codigo_vehiculo=codigo_vehiculo, estado="en_cola").first()
    empleado = db_emp.query(Empleado).filter_by(codigo=codigo_empleado).first()

    if not vehiculo:
        mensaje = f"❌ El vehículo {codigo_vehiculo} no está disponible en cola."
    elif not empleado:
        mensaje = f"❌ El empleado con código {codigo_empleado} no existe."
    else:
        vehiculo.asignado_a = codigo_empleado
        db.commit()
        mensaje = f"✅ Vehículo {codigo_vehiculo} asignado a empleado {codigo_empleado}."

    # Volver a cargar la lista
    vehiculos = db.query(ColaLavado.codigo_vehiculo).filter_by(estado="en_cola").all()
    empleados = db_emp.query(Empleado.codigo).all()
    return templates.TemplateResponse("asignar.html", {
        "request": request,
        "vehiculos": [v[0] for v in vehiculos],
        "empleados": [e[0] for e in empleados],
        "mensaje": mensaje
    })
