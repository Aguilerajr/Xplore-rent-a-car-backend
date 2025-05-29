
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import sqlite3
import re

app = FastAPI()

# Endpoint existente (ejemplo de prueba, no eliminar los que ya tienes)
@app.get("/")
async def root():
    return {"message": "Backend funcionando correctamente"}

# Nuevo endpoint para agregar vehículos
@app.post("/agregar_vehiculo")
async def agregar_vehiculo(request: Request):
    data = await request.json()
    letra = data.get("letra")
    digitos = data.get("digitos")

    # Validar letra: debe ser una sola letra entre P, C, M, T (mayúscula)
    if letra not in ["P", "C", "M", "T"]:
        raise HTTPException(status_code=400, detail="La letra debe ser P, C, M o T (mayúscula).")

    # Validar que los dígitos sean 4 dígitos numéricos
    if not re.fullmatch(r"\\d{4}", digitos):
        raise HTTPException(status_code=400, detail="Los dígitos deben ser exactamente 4 números.")

    # Formatear el código final
    codigo_vehiculo = f"{letra}-{digitos}"

    # Conectar a la base de datos
    conn = sqlite3.connect("registros.db")
    cursor = conn.cursor()

    # Verificar si ya existe ese código
    cursor.execute("SELECT COUNT(*) FROM vehiculos WHERE codigo=?", (codigo_vehiculo,))
    existe = cursor.fetchone()[0]

    if existe:
        conn.close()
        raise HTTPException(status_code=400, detail="El código de vehículo ya existe.")

    # Insertar nuevo vehículo (aquí asumo que la tabla se llama 'vehiculos' y tiene la columna 'codigo')
    cursor.execute("INSERT INTO vehiculos (codigo) VALUES (?)", (codigo_vehiculo,))
    conn.commit()
    conn.close()

    return {"message": "Vehículo agregado correctamente", "codigo": codigo_vehiculo}
