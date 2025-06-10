from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import ColaLavado

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/panel_cola", response_class=HTMLResponse)
def mostrar_panel_cola(request: Request, db: Session = Depends(get_db)):
    cola = db.query(ColaLavado).order_by(ColaLavado.fecha).all()
    return templates.TemplateResponse("panel_cola.html", {
        "request": request,
        "cola_lavado": cola
    })
