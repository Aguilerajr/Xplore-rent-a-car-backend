from fastapi import APIRouter, Form, Query, Depends
from sqlalchemy.orm import Session
from database import get_db, get_db_empleados
from models import Clasificacion, ColaLavado, RegistroLavado, Empleado
from datetime import datetime

router = APIRouter()

# ✅ Verificar si un vehículo está disponible
@router.get("/verificar_disponibilidad")
def verificar_disponibilidad(codigo: str = Query(...), db: Session = Depends(get_db)):
    clasificado = db.query(Clasificacion).filter_by(codigo=codigo).first()
    en_cola = db.query(ColaLavado).filter(
        ColaLavado.codigo_vehiculo == codigo,
        ColaLavado.estado.in_(["en_cola", "en_proceso"])
    ).first()
    return {"disponible": bool(clasificado and en_cola)}


# ✅ Check-in del lavador
@router.post("/checkin")
def checkin(
    codigo: str = Form(...),
    empleado: str = Form(...),
    inicio: str = Form(...),
    db: Session = Depends(get_db),
    db_emp: Session = Depends(get_db_empleados)
):
    # Validar check-in activo
    if db.query(RegistroLavado).filter_by(empleado=empleado, fin=None).first():
        return {"error": "Ya tienes un check-in activo"}

    # Verificar clasificación y cola
    clasificacion = db.query(Clasificacion).filter_by(codigo=codigo).first()
    en_cola = db.query(ColaLavado).filter(
        ColaLavado.codigo_vehiculo == codigo,
        ColaLavado.estado.in_(["en_cola", "en_proceso"])
    ).first()
    if not clasificacion or not en_cola:
        return {"error": "Vehículo no clasificado o ya finalizado"}

    # Parsear fecha
    try:
        inicio_dt = datetime.strptime(inicio, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return {"error": f"Formato inválido de fecha: {e}"}

    # Obtener nombre
    emp = db_emp.query(Empleado).filter_by(codigo=empleado).first()
    nombre = emp.nombre if emp else "Desconocido"

    # Crear registro
    registro = RegistroLavado(
        vehiculo=codigo,
        empleado=empleado,
        nombre_empleado=nombre,
        inicio=inicio_dt,
        fin=None,
        tiempo_real=0,
        tiempo_estimado=clasificacion.tiempo_estimado,
        eficiencia="0%"
    )
    db.add(registro)

    # Marcar en_proceso si estaba en_cola
    if en_cola.estado == "en_cola":
        en_cola.estado = "en_proceso"

    db.commit()
    return {"status": "checkin exitoso"}


# ✅ Registrar el lavado (check-out)
@router.post("/registrar")
def registrar_lavado(
    codigo: str = Form(...),
    empleado: str = Form(...),
    inicio: str = Form(...),
    fin: str = Form(...),
    db: Session = Depends(get_db),
    db_emp: Session = Depends(get_db_empleados)
):
    try:
        inicio_dt = datetime.strptime(inicio, "%Y-%m-%d %H:%M:%S")
        fin_dt = datetime.strptime(fin, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return {"error": f"Error en formato de fecha: {str(e)}"}

    tiempo_real = int((fin_dt - inicio_dt).total_seconds() / 60)

    clasificacion = db.query(Clasificacion).filter_by(codigo=codigo).first()
    if not clasificacion:
        return {"error": "Vehículo no clasificado"}

    registro = db.query(RegistroLavado).filter_by(
        vehiculo=codigo, empleado=empleado, fin=None
    ).first()

    if not registro:
        return {"error": "No se encontró un check-in activo para este empleado y vehículo"}

    emp = db_emp.query(Empleado).filter_by(codigo=empleado).first()
    nombre = emp.nombre if emp else "Desconocido"

    eficiencia = round((clasificacion.tiempo_estimado / tiempo_real) * 100, 1) if tiempo_real > 0 else 0

    # Actualiza el registro
    registro.fin = fin_dt
    registro.tiempo_real = tiempo_real
    registro.eficiencia = f"{eficiencia}%"
    registro.nombre_empleado = nombre

    db.query(ColaLavado).filter_by(codigo_vehiculo=codigo).update({"estado": "completado"})
    db.commit()

    # Eliminar si ya no hay nadie más lavando
    restantes = db.query(RegistroLavado).filter_by(vehiculo=codigo, fin=None).count()
    if restantes == 0:
        db.query(ColaLavado).filter_by(codigo_vehiculo=codigo).delete()
        db.query(Clasificacion).filter_by(codigo=codigo).delete()
        db.commit()

    return {"status": "ok", "eficiencia": eficiencia}
