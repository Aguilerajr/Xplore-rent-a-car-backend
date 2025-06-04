from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from routes.clasificacion import router as clasificacion_router
from routes.lavado import router as lavado_router
from routes.empleados import router as empleados_router
from routes.vehiculos import router as vehiculos_router

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Incluir rutas
app.include_router(clasificacion_router)
app.include_router(lavado_router)
app.include_router(empleados_router)
app.include_router(vehiculos_router)
