from fastapi import APIRouter, Form, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import Vehiculo
import re

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# ✅ Verificador de sesión específica para agregar vehículo
def verificar_sesion_vehiculo(request: Request):
    if not request.session.get("autorizado_vehiculo"):
        raise HTTPException(status_code=401, detail="No autorizado")

@router.get("/agregar_vehiculo", response_class=HTMLResponse)
def mostrar_formulario_vehiculo(
    request: Request,
    autorizado: bool = Depends(verificar_sesion_vehiculo)
):
    return templates.TemplateResponse("agregar_vehiculo.html", {"request": request, "mensaje": ""})

@router.post("/agregar_vehiculo", response_class=HTMLResponse)
def agregar_vehiculo(
    request: Request,
    codigo: str = Form(...),
    marca: str = Form(...),
    modelo: str = Form(...),
    tipo: str = Form(...),
    db: Session = Depends(get_db),
    autorizado: bool = Depends(verificar_sesion_vehiculo)
):
    if not re.fullmatch(r"[A-Z]{1,3}-\d{4}", codigo):
        mensaje = "❌ Código inválido. Debe tener formato como ABC-1234"
    elif db.query(Vehiculo).filter_by(codigo=codigo).first():
        mensaje = "❌ El vehículo ya existe."
    else:
        digitos = codigo.split("-")[1]
        vehiculos_con_mismo_numero = db.query(Vehiculo).filter(Vehiculo.codigo.like(f"%-{digitos}")).first()
        if vehiculos_con_mismo_numero:
            mensaje = f"❌ Ya existe un vehículo con el número {digitos} (sin importar la letra)."
        else:
            nuevo_vehiculo = Vehiculo(codigo=codigo, marca=marca, modelo=modelo, tipo=tipo)
            db.add(nuevo_vehiculo)
            db.commit()
            mensaje = f"✅ Vehículo {codigo} agregado correctamente."

    return templates.TemplateResponse("agregar_vehiculo.html", {
        "request": request,
        "mensaje": mensaje
    })
