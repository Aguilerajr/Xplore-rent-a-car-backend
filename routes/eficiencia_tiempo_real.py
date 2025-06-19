from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, get_db_empleados
from models import RegistroLavado, Empleado
from datetime import datetime, timedelta
from sqlalchemy import func

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/eficiencia_tiempo_real", response_class=HTMLResponse)
def dashboard_eficiencia(request: Request):
    """Página principal del dashboard de eficiencia en tiempo real"""
    return templates.TemplateResponse("eficiencia_tiempo_real.html", {"request": request})

@router.get("/api/eficiencia_actual")
def obtener_eficiencia_actual(
    db: Session = Depends(get_db),
    db_empleados: Session = Depends(get_db_empleados)
):
    """API endpoint que devuelve la eficiencia actual de todos los empleados"""
    
    # Obtener el inicio de la semana actual (lunes)
    hoy = datetime.now()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_semana = inicio_semana.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Obtener todos los empleados
    empleados = db_empleados.query(Empleado).all()
    
    # Calcular eficiencia para cada empleado
    datos_eficiencia = []
    
    for empleado in empleados:
        # Obtener registros de lavado de la semana actual para este empleado
        registros = db.query(RegistroLavado).filter(
            RegistroLavado.empleado == empleado.codigo,
            RegistroLavado.inicio >= inicio_semana,
            RegistroLavado.fin.isnot(None)  # Solo registros completados
        ).all()
        
        if registros:
            # Calcular eficiencia promedio
            total_estimado = sum(r.tiempo_estimado for r in registros)
            total_real = sum(r.tiempo_real for r in registros)
            vehiculos_lavados = len(registros)
            
            if total_real > 0:
                eficiencia = round((total_estimado / total_real) * 100, 1)
            else:
                eficiencia = 0
        else:
            eficiencia = 0
            vehiculos_lavados = 0
            total_estimado = 0
            total_real = 0
        
        # Verificar si el empleado está actualmente lavando
        lavando_ahora = db.query(RegistroLavado).filter(
            RegistroLavado.empleado == empleado.codigo,
            RegistroLavado.fin.is_(None)
        ).first()
        
        estado = "Lavando" if lavando_ahora else "Disponible"
        vehiculo_actual = lavando_ahora.vehiculo if lavando_ahora else None
        
        datos_eficiencia.append({
            "codigo": empleado.codigo,
            "nombre": empleado.nombre,
            "eficiencia": eficiencia,
            "vehiculos_lavados": vehiculos_lavados,
            "tiempo_estimado_total": total_estimado,
            "tiempo_real_total": total_real,
            "estado": estado,
            "vehiculo_actual": vehiculo_actual
        })
    
    # Ordenar por eficiencia descendente
    datos_eficiencia.sort(key=lambda x: x["eficiencia"], reverse=True)
    
    return {
        "empleados": datos_eficiencia,
        "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "semana_inicio": inicio_semana.strftime("%Y-%m-%d")
    }

@router.get("/api/estadisticas_generales")
def obtener_estadisticas_generales(
    db: Session = Depends(get_db),
    db_empleados: Session = Depends(get_db_empleados)
):
    """API endpoint que devuelve estadísticas generales del día y la semana"""
    
    # Obtener fechas
    hoy = datetime.now()
    inicio_dia = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_semana = inicio_semana.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Estadísticas del día
    registros_hoy = db.query(RegistroLavado).filter(
        RegistroLavado.inicio >= inicio_dia,
        RegistroLavado.fin.isnot(None)
    ).all()
    
    vehiculos_hoy = len(registros_hoy)
    eficiencia_promedio_hoy = 0
    if registros_hoy:
        total_est_hoy = sum(r.tiempo_estimado for r in registros_hoy)
        total_real_hoy = sum(r.tiempo_real for r in registros_hoy)
        if total_real_hoy > 0:
            eficiencia_promedio_hoy = round((total_est_hoy / total_real_hoy) * 100, 1)
    
    # Estadísticas de la semana
    registros_semana = db.query(RegistroLavado).filter(
        RegistroLavado.inicio >= inicio_semana,
        RegistroLavado.fin.isnot(None)
    ).all()
    
    vehiculos_semana = len(registros_semana)
    eficiencia_promedio_semana = 0
    if registros_semana:
        total_est_semana = sum(r.tiempo_estimado for r in registros_semana)
        total_real_semana = sum(r.tiempo_real for r in registros_semana)
        if total_real_semana > 0:
            eficiencia_promedio_semana = round((total_est_semana / total_real_semana) * 100, 1)
    
    # Empleados activos ahora
    empleados_activos = db.query(RegistroLavado).filter(
        RegistroLavado.fin.is_(None)
    ).count()
    
    return {
        "hoy": {
            "vehiculos_lavados": vehiculos_hoy,
            "eficiencia_promedio": eficiencia_promedio_hoy
        },
        "semana": {
            "vehiculos_lavados": vehiculos_semana,
            "eficiencia_promedio": eficiencia_promedio_semana
        },
        "empleados_activos": empleados_activos,
        "fecha_actual": hoy.strftime("%Y-%m-%d %H:%M:%S")
    }
