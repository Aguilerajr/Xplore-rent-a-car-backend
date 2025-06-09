from fastapi import APIRouter, Form, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db_empleados
from models import Empleado
import re

router = APIRouter()
templates = Jinja2Templates(directory="templates")

CLAVE_ACCESO = "admin123"  # Puedes cambiarla

@router.get("/agregar_empleado", response_class=HTMLResponse)
def mostrar_formulario_empleado(request: Request):
    return templates.TemplateResponse("agregar_empleado.html", {"request": request, "mensaje": ""})

@router.post("/agregar_empleado", response_class=HTMLResponse)
def agregar_empleado(
    request: Request,
    codigo: str = Form(...),
    nombre: str = Form(...),
    db: Session = Depends(get_db_empleados)
):
    
    if not re.fullmatch(r"\d{4}", codigo):
        mensaje = "❌ El código debe tener 4 dígitos."
    elif db.query(Empleado).filter_by(codigo=codigo).first():
        mensaje = "❌ El empleado ya existe."
    else:
        db.add(Empleado(codigo=codigo, nombre=nombre))
        db.commit()
        mensaje = f"✅ Empleado {nombre} agregado."

    return templates.TemplateResponse("agregar_empleado.html", {"request": request, "mensaje": mensaje})
