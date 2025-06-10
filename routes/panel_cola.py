from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import ColaLavado
from datetime import datetime


router = APIRouter()
templates = Jinja2Templates(directory="templates")

# ✅ Función que traduce el código como "D2" a una descripción legible
def descripcion_clasificacion(codigo):
    mapa_suciedad = {
        "1": "Muy sucio", "2": "Normal", "3": "Poco sucio",
        "4": "Shampuseado", "5": "Franeleado"
    }
    mapa_tipo = {
        "A": "Camioneta Grande", "B": "Camioneta pequeña", "C": "Busito",
        "D": "Pick Up", "E": "Turismo normal", "F": "Turismo pequeño"
    }

    if not codigo or len(codigo) < 2:
        return "Desconocido"

    suciedad = mapa_suciedad.get(codigo[0], "Desconocido")
    tipo = mapa_tipo.get(codigo[1], "Desconocido")
    return f"{suciedad} - {tipo}"

@router.get("/panel_cola", response_class=HTMLResponse)
def mostrar_panel_cola(request: Request, db: Session = Depends(get_db)):
    cola = db.query(ColaLavado).order_by(ColaLavado.fecha).all()
    return templates.TemplateResponse("panel_cola.html", {
    "request": request,
    "cola_lavado": cola,
    "descripcion_clasificacion": descripcion_clasificacion,
    "now": datetime.now()  # ✅ añadido
})

