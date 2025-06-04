from fastapi import APIRouter, Form, Depends
from sqlalchemy.orm import Session
from database import get_db, get_db_empleados
from models import Clasificacion, ColaLavado, RegistroLavado, Empleado
from datetime import datetime

router = APIRouter()

@router.post("/checkin")
def checkin(codigo: str = Form(...), empleado: str = Form(...), db: Session = Depends(get_db), db_emp: Session = Depends(get_db_empleados)):
    activo = db.query(RegistroLavado).filter_by(empleado=empleado, fin=None).first()
    if activo:
        return {"error": "Ya tienes un check-in activo"}

    clasificacion = db.query(Clasificacion).filter_by(codigo=codigo).first()
    en_cola = db.query(ColaLavado).filter_by(codigo_vehiculo=codigo, estado="en_cola").first()
    if not clasificacion or not en_cola:
        return {"error": "Vehículo no disponible"}

    emp = db_emp.query(Empleado).filter_by(codigo=empleado).first()
    nombre = emp.nombre if emp else "Desconocido"
    nuevo = RegistroLavado(
        vehiculo=codigo, empleado=empleado, nombre_empleado=nombre,
        inicio=datetime.utcnow(), fin=None,
        tiempo_real=0, tiempo_estimado=clasificacion.tiempo_estimado,
        eficiencia="0%"
    )
    db.add(nuevo)
    db.commit()
    return {"status": "checkin exitoso"}

@router.post("/registrar")
def registrar_lavado(codigo: str = Form(...), empleado: str = Form(...), inicio: str = Form(...), fin: str = Form(...), db: Session = Depends(get_db)):
    inicio_dt, fin_dt = datetime.fromisoformat(inicio), datetime.fromisoformat(fin)
    tiempo_real = int((fin_dt - inicio_dt).total_seconds() / 60)

    clasificacion = db.query(Clasificacion).filter_by(codigo=codigo).first()
    if not clasificacion:
        return {"error": "No clasificado"}

    eficiencia = round((clasificacion.tiempo_estimado / tiempo_real) * 100, 1) if tiempo_real > 0 else 0
    emp = Session(bind=db.get_bind()).query(Empleado).filter_by(codigo=empleado).first()
    nombre = emp.nombre if emp else "Desconocido"

    registro = db.query(RegistroLavado).filter_by(vehiculo=codigo, empleado=empleado, fin=None).first()
    if registro:
        registro.fin = fin_dt
        registro.tiempo_real = tiempo_real
        registro.eficiencia = f"{eficiencia}%"
    else:
        return {"error": "No hay check-in previo"}

    db.query(ColaLavado).filter_by(codigo_vehiculo=codigo).update({"estado": "completado"})
    activos = db.query(RegistroLavado).filter_by(vehiculo=codigo, fin=None).count()
    if activos == 0:
        db.query(ColaLavado).filter_by(codigo_vehiculo=codigo).delete()
        db.query(Clasificacion).filter_by(codigo=codigo).delete()

    db.commit()
    return {"status": "ok", "eficiencia": eficiencia}
