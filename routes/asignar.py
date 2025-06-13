from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, get_db_empleados
from models import ColaLavado, Empleado

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/asignar", response_class=HTMLResponse)
def mostrar_asignacion(request: Request, db: Session = Depends(get_db)):
    vehiculos_en_cola = db.query(ColaLavado.codigo_vehiculo).filter_by(estado="en_cola").all()
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
    empleados: list[str] = Form(...),
    db: Session = Depends(get_db),
    db_emp: Session = Depends(get_db_empleados)
):
    vehiculo_obj = db.query(ColaLavado).filter_by(codigo_vehiculo=vehiculo, estado="en_cola").first()

    if not vehiculo_obj:
        mensaje = f"❌ El vehículo {vehiculo} no está en cola."
    else:
        asignados = vehiculo_obj.asignado_a.split(",") if vehiculo_obj.asignado_a else []
        mensajes = []
        for emp_codigo in empleados:
            emp = db_emp.query(Empleado).filter_by(codigo=emp_codigo).first()
            if not emp:
                mensajes.append(f"❌ Empleado {emp_codigo} no existe.")
            elif emp_codigo in asignados:
                mensajes.append(f"⚠️ Empleado {emp_codigo} ya estaba asignado.")
            else:
                asignados.append(emp_codigo)
                mensajes.append(f"✅ Vehículo {vehiculo} asignado a empleado {emp_codigo}.")

        vehiculo_obj.asignado_a = ",".join(asignados)
        db.commit()
        mensaje = "<br>".join(mensajes)

    vehiculos_en_cola = db.query(ColaLavado.codigo_vehiculo).filter_by(estado="en_cola").all()
    disponibles = [v[0] for v in vehiculos_en_cola]

    return templates.TemplateResponse("asignar.html", {
        "request": request,
        "vehiculos": disponibles,
        "mensaje": mensaje
    })

@router.get("/buscar_empleados")
def buscar_empleados(q: str, db: Session = Depends(get_db_empleados)):
    resultados = db.query(Empleado.codigo).filter(Empleado.codigo.ilike(f"%{q}%")).all()
    return {"resultados": [r[0] for r in resultados]}

@router.get("/buscar_codigos")
def buscar_codigos(q: str, db: Session = Depends(get_db)):
    resultados = db.query(ColaLavado.codigo_vehiculo).filter(
        ColaLavado.codigo_vehiculo.ilike(f"%{q}%"),
        ColaLavado.estado == "en_cola"
    ).all()
    return {"resultados": [r[0] for r in resultados]}
