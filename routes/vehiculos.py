from fastapi import APIRouter, Form, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import Vehiculo
import re

router = APIRouter()
templates = Jinja2Templates(directory="templates")

CLAVE_ACCESO = "admin123"  # puedes cambiar esta clave

@router.get("/agregar_vehiculo", response_class=HTMLResponse)
def mostrar_formulario_vehiculo(request: Request):
    return templates.TemplateResponse("agregar_vehiculo.html", {"request": request, "mensaje": ""})

@router.post("/agregar_vehiculo", response_class=HTMLResponse)
def agregar_vehiculo(
    request: Request,
    codigo: str = Form(...),
    db: Session = Depends(get_db)
):
    # Validación de formato
    if not re.fullmatch(r"[A-Z]{1,3}-\d{4}", codigo):
        mensaje = "❌ Código inválido. Debe tener formato como ABC-1234"

    # Validación por código exacto
    elif db.query(Vehiculo).filter_by(codigo=codigo).first():
        mensaje = "❌ El vehículo ya existe."

    else:
        # Extraer los 4 dígitos
        digitos = codigo.split("-")[1]

        # Validar duplicado de número aunque cambie la letra
        vehiculos_con_mismo_numero = db.query(Vehiculo).filter(Vehiculo.codigo.like(f"%-{digitos}")).first()

        if vehiculos_con_mismo_numero:
            mensaje = f"❌ Ya existe un vehículo con el número {digitos} (sin importar la letra)."
        else:
            db.add(Vehiculo(codigo=codigo))
            db.commit()
            mensaje = f"✅ Vehículo {codigo} agregado correctamente."

    return templates.TemplateResponse("agregar_vehiculo.html", {"request": request, "mensaje": mensaje})
