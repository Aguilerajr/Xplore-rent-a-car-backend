from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path

# Importar routers personalizados
from backend1.routes.clasificacion import router as clasificacion_router
from backend1.routes.lavado import router as lavado_router
from backend1.routes.empleados import router as empleados_router
from backend1.routes.vehiculos import router as vehiculos_router
from backend1.routes.codigos import router as codigos_router
from backend1.routes.admin_panel import router as admin_panel_router
from backend1.routes.reporte_semanal import router as reporte_router
from backend1.routes.reporte_formulario import router as reporte_formulario_router
from backend1.routes.eficiencia_tiempo_real import router as eficiencia_router
from backend1.routes import panel_cola

app = FastAPI()

# Configuración de rutas y templates
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Página principal
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Montar routers
app.include_router(clasificacion_router)
app.include_router(lavado_router)
app.include_router(empleados_router)
app.include_router(vehiculos_router)
app.include_router(codigos_router)
app.include_router(admin_panel_router)
app.include_router(reporte_router)
app.include_router(reporte_formulario_router)
app.include_router(eficiencia_router)
app.include_router(panel_cola.router)
