from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

CLAVE_ACCESO = "admin123"

@router.get("/verificar_agregar_vehiculo", response_class=HTMLResponse)
def mostrar_formulario_vehiculo(request: Request):
    return templates.TemplateResponse("verificar_clave.html", {
        "request": request,
        "destino": "/agregar_vehiculo"
    })

@router.post("/verificar_agregar_vehiculo", response_class=HTMLResponse)
def verificar_vehiculo(request: Request, clave: str = Form(...)):
    if clave == CLAVE_ACCESO:
        return RedirectResponse(url="/agregar_vehiculo", status_code=302)
    return templates.TemplateResponse("verificar_clave.html", {
        "request": request,
        "error": "❌ Contraseña incorrecta",
        "destino": "/agregar_vehiculo"
    })


# 🔒 PROTECCIÓN PARA AGREGAR EMPLEADO

@router.get("/verificar_agregar_empleado", response_class=HTMLResponse)
def mostrar_formulario_empleado(request: Request):
    return templates.TemplateResponse("verificar_clave.html", {
        "request": request,
        "destino": "/agregar_empleado"
    })

@router.post("/verificar_agregar_empleado", response_class=HTMLResponse)
def verificar_empleado(request: Request, clave: str = Form(...)):
    if clave == CLAVE_ACCESO:
        return RedirectResponse(url="/agregar_empleado", status_code=302)
    return templates.TemplateResponse("verificar_clave.html", {
        "request": request,
        "error": "❌ Contraseña incorrecta",
        "destino": "/agregar_empleado"
    })
