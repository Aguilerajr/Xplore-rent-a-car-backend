from fastapi import APIRouter, Form, Depends
from sqlalchemy.orm import Session
from database import get_db_empleados
from models import Empleado

router = APIRouter()

@router.post("/login")
def login(codigo: str = Form(...), db: Session = Depends(get_db_empleados)):
    empleado = db.query(Empleado).filter_by(codigo=codigo.strip()).first()
    if empleado:
        return {"status": "ok", "codigo": empleado.codigo, "nombre": empleado.nombre}
    return {"status": "error", "message": "Código no válido"}
