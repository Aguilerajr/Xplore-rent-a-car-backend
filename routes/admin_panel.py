
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, get_db_empleados
from models import Vehiculo, Clasificacion, ColaLavado, RegistroLavado, Empleado

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/admin_panel", response_class=HTMLResponse)
def mostrar_panel_admin(request: Request, db: Session = Depends(get_db), db_emp: Session = Depends(get_db_empleados)):
    vehiculos = db.query(Vehiculo).all()
    empleados = db_emp.query(Empleado).all()
    registros = db.query(RegistroLavado).order_by(RegistroLavado.id.desc()).limit(10).all()
    return templates.TemplateResponse("admin_panel.html", {
        "request": request,
        "vehiculos": vehiculos,
        "empleados": empleados,
        "registros": registros
    })

@router.get("/admin_panel/editar_vehiculo/{codigo}", response_class=HTMLResponse)
def editar_vehiculo_get(codigo: str, request: Request, db: Session = Depends(get_db)):
    vehiculo = db.query(Vehiculo).filter_by(codigo=codigo).first()
    if not vehiculo:
        return HTMLResponse(content="Vehículo no encontrado", status_code=404)
    return templates.TemplateResponse("editar_vehiculo.html", {"request": request, "vehiculo": vehiculo})

@router.post("/admin_panel/editar_vehiculo/{codigo}", response_class=HTMLResponse)
def editar_vehiculo_post(codigo: str, request: Request, marca: str = Form(...), modelo: str = Form(...), tipo: str = Form(...), db: Session = Depends(get_db)):
    vehiculo = db.query(Vehiculo).filter_by(codigo=codigo).first()
    if not vehiculo:
        return HTMLResponse(content="Vehículo no encontrado", status_code=404)
    vehiculo.marca = marca
    vehiculo.modelo = modelo
    vehiculo.tipo = tipo
    db.commit()
    return RedirectResponse("/admin_panel", status_code=302)

@router.get("/admin_panel/editar_empleado/{codigo}", response_class=HTMLResponse)
def editar_empleado_get(codigo: str, request: Request, db: Session = Depends(get_db_empleados)):
    empleado = db.query(Empleado).filter_by(codigo=codigo).first()
    if not empleado:
        return HTMLResponse(content="Empleado no encontrado", status_code=404)
    return templates.TemplateResponse("editar_empleado.html", {"request": request, "empleado": empleado})

@router.post("/admin_panel/editar_empleado/{codigo}", response_class=HTMLResponse)
def editar_empleado_post(codigo: str, request: Request, nombre: str = Form(...), db: Session = Depends(get_db_empleados)):
    empleado = db.query(Empleado).filter_by(codigo=codigo).first()
    if not empleado:
        return HTMLResponse(content="Empleado no encontrado", status_code=404)
    empleado.nombre = nombre
    db.commit()
    return RedirectResponse("/admin_panel", status_code=302)
