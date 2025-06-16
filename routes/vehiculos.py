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
    letra: str = Form(...),
    numero: str = Form(...),
    marca: str = Form(...),
    modelo: str = Form(...),
    tipo: str = Form(...),
    db: Session = Depends(get_db)
):
    codigo = f"{letra}-{numero}"

    # Validar formato general
    if not re.fullmatch(r"[A-Z]{1}-\d{4}", codigo):
        mensaje = "❌ Código inválido. Debe tener formato como D-1234"

    elif db.query(Vehiculo).filter_by(codigo=codigo).first():
        mensaje = "❌ El vehículo ya existe."

    else:
        # Validar duplicado de número sin importar letra
        vehiculos_con_mismo_numero = db.query(Vehiculo).filter(Vehiculo.codigo.like(f"%-{numero}")).first()

        if vehiculos_con_mismo_numero:
            mensaje = f"❌ Ya existe un vehículo con el número {numero} (sin importar la letra)."
        else:
            nuevo_vehiculo = Vehiculo(codigo=codigo, marca=marca, modelo=modelo, tipo=tipo)
            db.add(nuevo_vehiculo)
            db.commit()
            mensaje = f"✅ Vehículo {codigo} agregado correctamente."

    return templates.TemplateResponse("agregar_vehiculo.html", {
        "request": request,
        "mensaje": mensaje
    })
