from fastapi import FastAPI, Form, Depends
from sqlalchemy import create_engine, Column, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from contextlib import asynccontextmanager
import re

# Conexión a la base de datos de usuarios
DATABASE_URL_USUARIOS = "postgresql://postgres:gFQOssQuCNFeLZqvKBNcERsRrxWEiZlJ@shuttle.proxy.rlwy.net:42664/railway"

engine_usuarios = create_engine(DATABASE_URL_USUARIOS)
SessionUsuarios = sessionmaker(autocommit=False, autoflush=False, bind=engine_usuarios)
BaseUsuarios = declarative_base()

class Empleado(BaseUsuarios):
    __tablename__ = "empleados"
    codigo = Column(String(4), primary_key=True)
    nombre = Column(String, nullable=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    BaseUsuarios.metadata.create_all(bind=engine_usuarios)
    yield

app = FastAPI(lifespan=lifespan)

def get_db():
    db = SessionUsuarios()
    try:
        yield db
    finally:
        db.close()

@app.post("/agregar_empleado")
def agregar_empleado(codigo: str = Form(...), nombre: str = Form(...), db: Session = Depends(get_db)):
    if not re.fullmatch(r"\d{4}", codigo):
        return {"status": "error", "message": "❌ El código debe tener 4 dígitos numéricos."}
    if db.query(Empleado).filter_by(codigo=codigo).first():
        return {"status": "error", "message": "❌ El empleado ya existe."}
    db.add(Empleado(codigo=codigo, nombre=nombre))
    db.commit()
    return {"status": "success", "message": f"✅ Empleado {nombre} agregado con código {codigo}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("usuarios:app", host="0.0.0.0", port=8001)
