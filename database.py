from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Leer variables de entorno (con valores por defecto para pruebas locales)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:nBdGeUvCIPjXTDNhygtqTqMxUumrlvkN@shuttle.proxy.rlwy.net:10389/railway"
)

DATABASE_URL_EMPLEADOS = os.getenv(
    "DATABASE_EMPLEADOS",
    "postgresql://postgres:gFQOssQuCNFeLZqvKBNcERsRrxWEiZlJ@shuttle.proxy.rlwy.net:42664/railway"
)

# Conexión principal (vehículos)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Conexión empleados
engine_empleados = create_engine(DATABASE_URL_EMPLEADOS)
SessionEmpleados = sessionmaker(autocommit=False, autoflush=False, bind=engine_empleados)
BaseEmpleados = declarative_base()

# Funciones de sesión para FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_empleados():
    db = SessionEmpleados()
    try:
        yield db
    finally:
        db.close()
