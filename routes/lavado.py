from fastapi import APIRouter, Form, Depends
from sqlalchemy.orm import Session
from database import get_db, get_db_empleados
from models import Clasificacion, ColaLavado, RegistroLavado, Empleado
from datetime import datetime

router = APIRouter()

@router.post("/checkin")
def checkin(
    codigo: str = Form(...),
    empleado: str = Form(...),
    inicio: str = Form(...),
    db: Session = Depends(get_db),
    db_emp: Session = Depends(get_db_empleados)
):
    # Verificar si el empleado ya tiene un check-in activo
    activo = db.query(RegistroLavado).filter_by(empleado=empleado, fin=None).first()
    if activo:
        return {"error": "Ya tienes un check-in activo"}

    # Verificar que el vehículo esté clasificado
    clasificacion = db.query(Clasificacion).filter_by(codigo=codigo).first()
    if not clasificacion:
        return {"error": "Vehículo no está clasificado"}

    # Verificar que el vehículo esté en cola o en progreso
    cola = db.query(ColaLavado).filter(
        ColaLavado.codigo_vehiculo == codigo,
        ColaLavado.estado.in_(["en_cola", "en_progreso"])
    ).first()
    if not cola:
        return {"error": "Vehículo no está disponible (posiblemente ya finalizado)"}

    # Si el vehículo está en cola, actualizar estado a "en_progreso"
    if cola.estado == "en_cola":
        cola.estado = "en_progreso"
        db.commit()

    # Obtener nombre del empleado
    emp = db_emp.query(Empleado).filter_by(codigo=empleado).first()
    nombre = emp.nombre if emp else "Desconocido"

    # Parsear fecha de inicio
    try:
        inicio_dt = datetime.strptime(inicio, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return {"error": f"Formato de fecha inválido: {str(e)}"}

    # Crear registro de lavado
    nuevo = RegistroLavado(
        vehiculo=codigo,
        empleado=empleado,
        nombre_empleado=nombre,
        inicio=inicio_dt,
        fin=None,
        tiempo_real=0,
        tiempo_estimado=clasificacion.tiempo_estimado,
        eficiencia="0%"
    )
    db.add(nuevo)
    db.commit()

    return {"status": "checkin exitoso"}


@router.post("/registrar")
def registrar_lavado(
    codigo: str = Form(...),
    empleado: str = Form(...),
    inicio: str = Form(...),
    fin: str = Form(...),
    db: Session = Depends(get_db),
    db_emp: Session = Depends(get_db_empleados)
):
    # Parsear fechas
    try:
        inicio_dt = datetime.strptime(inicio, "%Y-%m-%d %H:%M:%S")
        fin_dt = datetime.strptime(fin, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return {"error": f"Error en formato de fecha: {str(e)}"}

    tiempo_real = int((fin_dt - inicio_dt).total_seconds() / 60)

    # Verificar clasificación
    clasificacion = db.query(Clasificacion).filter_by(codigo=codigo).first()
    if not clasificacion:
        return {"error": "No clasificado"}

    eficiencia = round((clasificacion.tiempo_estimado / tiempo_real) * 100, 1) if tiempo_real > 0 else 0

    emp = db_emp.query(Empleado).filter_by(codigo=empleado).first()
    nombre = emp.nombre if emp else "Desconocido"

    # Buscar el registro activo
    registro = db.query(RegistroLavado).filter_by(
        vehiculo=codigo,
        empleado=empleado,
        fin=None
    ).first()

    if not registro:
        return {"error": "No hay check-in previo"}

    # Cerrar el registro
    registro.fin = fin_dt
    registro.tiempo_real = tiempo_real
    registro.eficiencia = f"{eficiencia}%"
    db.commit()

    # Si ya nadie más está lavando ese vehículo, eliminarlo de la cola y clasificaciones
    activos = db.query(RegistroLavado).filter_by(vehiculo=codigo, fin=None).count()
    if activos == 0:
        db.query(ColaLavado).filter_by(codigo_vehiculo=codigo).delete()
        db.query(Clasificacion).filter_by(codigo=codigo).delete()
        db.commit()

    return {"status": "ok", "eficiencia": eficiencia}


@router.post("/verificar_disponibilidad")
def verificar_disponibilidad(
    codigo: str = Form(...),
    db: Session = Depends(get_db)
):
    # Verificar si está clasificado
    clasificado = db.query(Clasificacion).filter_by(codigo=codigo).first()
    if not clasificado:
        return {"disponible": False}

    # Verificar si está en cola o en progreso
    cola = db.query(ColaLavado).filter(
        ColaLavado.codigo_vehiculo == codigo,
        ColaLavado.estado.in_(["en_cola", "en_progreso"])
    ).first()

    return {"disponible": bool(cola)}
