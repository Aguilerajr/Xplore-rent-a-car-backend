from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, get_db_empleados
from models import Vehiculo, Clasificacion, ColaLavado, RegistroLavado, Empleado

router = APIRouter()
templates = Jinja2Templates(directory="templates")

CLAVE_ADMIN = "admin123"

@router.get("/admin_login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request, "error": ""})

@router.post("/admin_login", response_class=HTMLResponse)
def admin_login(request: Request, clave: str = Form(...)):
    if clave == CLAVE_ADMIN:
        return RedirectResponse("/admin_panel", status_code=302)
    return templates.TemplateResponse("admin_login.html", {"request": request, "error": "❌ Contraseña incorrecta"})

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
