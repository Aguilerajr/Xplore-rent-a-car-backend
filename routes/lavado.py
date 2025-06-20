from fastapi import APIRouter, Form, Query, Depends
from sqlalchemy.orm import Session
from database import get_db, get_db_empleados
from models import Clasificacion, ColaLavado, RegistroLavado, Empleado
from datetime import datetime

router = APIRouter()

# Verificar disponibilidad
@router.get("/verificar_disponibilidad")
def verificar_disponibilidad(codigo: str = Query(...), db: Session = Depends(get_db)):
    clasificado = db.query(Clasificacion).filter_by(codigo=codigo).first()
    en_cola = db.query(ColaLavado).filter(
        ColaLavado.codigo_vehiculo == codigo,
        ColaLavado.estado.in_(["en_cola", "en_proceso"])
    ).first()
    en_lavado = db.query(RegistroLavado).filter(
        RegistroLavado.vehiculo == codigo,
        RegistroLavado.fin.is_(None)
    ).first()
    return {"disponible": bool(clasificado or en_cola or en_lavado)}

# Check-in
@router.post("/checkin")
def checkin(
    codigo: str = Form(...),
    empleado: str = Form(...),
    inicio: str = Form(...),
    db: Session = Depends(get_db),
    db_emp: Session = Depends(get_db_empleados)
):
    if db.query(RegistroLavado).filter_by(empleado=empleado, fin=None).first():
        return {"status": "error", "mensaje": "Ya tienes un check-in activo"}

    clasificacion = db.query(Clasificacion).filter_by(codigo=codigo).first()
    en_cola = db.query(ColaLavado).filter(
        ColaLavado.codigo_vehiculo == codigo,
        ColaLavado.estado.in_(["en_cola", "en_proceso"])
    ).first()

    if not clasificacion or not en_cola:
        return {"status": "error", "mensaje": "Vehículo no clasificado o ya finalizado"}

    try:
        inicio_dt = datetime.strptime(inicio, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return {"status": "error", "mensaje": f"Formato inválido de fecha: {e}"}

    emp = db_emp.query(Empleado).filter_by(codigo=empleado).first()
    nombre = emp.nombre if emp else "Desconocido"

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

    if en_cola.estado == "en_cola":
        en_cola.estado = "en_proceso"

    db.commit()
    return {"status": "ok", "mensaje": "Check-in exitoso"}

# Check-out (MODIFICADO)
@router.post("/registrar")
def registrar_lavado(
    codigo: str = Form(...),
    empleado: str = Form(...),
    inicio: str = Form(...),  # todavía recibido pero no se usa
    fin: str = Form(...),
    db: Session = Depends(get_db),
    db_emp: Session = Depends(get_db_empleados)
):
    print("➡️ Iniciando proceso de CHECK-OUT")
    print(f"📌 Vehículo: {codigo}")
    print(f"👤 Empleado: {empleado}")
    print(f"⏱️ Fin: {fin}")

    try:
        fin_dt = datetime.strptime(fin, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return {"status": "error", "mensaje": f"Error en formato de fecha: {str(e)}"}

    # ✅ Buscar por vehículo y empleado sin depender de "inicio"
    registro = db.query(RegistroLavado).filter(
        RegistroLavado.vehiculo == codigo,
        RegistroLavado.empleado == empleado,
        RegistroLavado.fin.is_(None)
    ).order_by(RegistroLavado.inicio.desc()).first()

    if not registro:
        return {"status": "error", "mensaje": "No hay check-in previo para este empleado y vehículo"}

    clasificacion = db.query(Clasificacion).filter_by(codigo=registro.vehiculo).first()
    if not clasificacion:
        return {"status": "error", "mensaje": "Vehículo no clasificado"}

    tiempo_real = int((fin_dt - registro.inicio).total_seconds() / 60)
    eficiencia = round((clasificacion.tiempo_estimado / tiempo_real) * 100, 1) if tiempo_real > 0 else 0

    emp = db_emp.query(Empleado).filter_by(codigo=empleado).first()
    nombre = emp.nombre if emp else "Desconocido"

    registro.fin = fin_dt
    registro.tiempo_real = tiempo_real
    registro.eficiencia = f"{eficiencia}%"
    db.commit()

    activos = db.query(RegistroLavado).filter(
        RegistroLavado.vehiculo == codigo,
        RegistroLavado.fin.is_(None)
    ).count()

    if activos == 0:
        db.query(ColaLavado).filter_by(codigo_vehiculo=codigo).delete()
        db.query(Clasificacion).filter_by(codigo=codigo).delete()
        db.commit()

    return {"status": "ok", "eficiencia": eficiencia}
