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
    codigo = codigo.strip().upper()
    empleado = empleado.strip()

    activo = db.query(RegistroLavado).filter_by(empleado=empleado, fin=None).first()
    if activo:
        return {"error": "Ya tienes un check-in activo"}

    clasificacion = db.query(Clasificacion).filter_by(codigo=codigo).first()
    if not clasificacion:
        return {"error": "Vehículo no está clasificado"}

    cola = db.query(ColaLavado).filter(
        ColaLavado.codigo_vehiculo == codigo,
        ColaLavado.estado.in_(["en_cola", "en_progreso"])
    ).first()
    if not cola:
        return {"error": "Vehículo no está disponible (posiblemente ya finalizado)"}

    if cola.estado == "en_cola":
        cola.estado = "en_progreso"
        db.commit()

    emp = db_emp.query(Empleado).filter_by(codigo=empleado).first()
    nombre = emp.nombre if emp else "Desconocido"

    try:
        inicio_dt = datetime.strptime(inicio, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return {"error": f"Formato de fecha inválido: {str(e)}"}

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
    codigo = codigo.strip().upper()
    empleado = empleado.strip()

    try:
        inicio_dt = datetime.strptime(inicio, "%Y-%m-%d %H:%M:%S")
        fin_dt = datetime.strptime(fin, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return {"error": f"Error en formato de fecha: {str(e)}"}

    tiempo_real = int((fin_dt - inicio_dt).total_seconds() / 60)

    clasificacion = db.query(Clasificacion).filter_by(codigo=codigo).first()
    if not clasificacion:
        return {"error": "No clasificado"}

    eficiencia = round((clasificacion.tiempo_estimado / tiempo_real) * 100, 1) if tiempo_real > 0 else 0

    emp = db_emp.query(Empleado).filter_by(codigo=empleado).first()
    nombre = emp.nombre if emp else "Desconocido"

    registro = db.query(RegistroLavado).filter_by(
        vehiculo=codigo,
        empleado=empleado,
        fin=None
    ).first()

    if not registro:
        return {"error": "No hay check-in previo"}

    registro.fin = fin_dt
    registro.tiempo_real = tiempo_real
    registro.eficiencia = f"{eficiencia}%"
    db.commit()

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
    codigo = codigo.strip().upper()

    clasificado = db.query(Clasificacion).filter_by(codigo=codigo).first()
    cola = db.query(ColaLavado).filter(
        ColaLavado.codigo_vehiculo == codigo,
        ColaLavado.estado.in_(["en_cola", "en_progreso"])
    ).first()

    return {
        "disponible": bool(clasificado and cola),
        "clasificado": clasificado is not None,
        "en_cola": cola is not None,
        "estado": cola.estado if cola else "finalizado"
    }


@router.get("/verificar/{codigo}")
def verificar_estado(codigo: str, db: Session = Depends(get_db)):
    codigo = codigo.strip().upper()
    clasificado = db.query(Clasificacion).filter_by(codigo=codigo).first()
    cola = db.query(ColaLavado).filter(
        ColaLavado.codigo_vehiculo == codigo,
        ColaLavado.estado.in_(["en_cola", "en_progreso"])
    ).first()

    return {
        "codigo": codigo,
        "clasificado": bool(clasificado),
        "cola": bool(cola),
        "estado": cola.estado if cola else "N/A"
    }
