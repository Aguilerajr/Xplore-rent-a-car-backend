
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/descargar_reporte", response_class=HTMLResponse)
def mostrar_formulario_reporte(request: Request):
    return templates.TemplateResponse("reporte.html", {"request": request})
