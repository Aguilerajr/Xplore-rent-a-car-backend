import sqlite3

# Crear o conectar a la base
conn = sqlite3.connect('registros.db')
cursor = conn.cursor()

# Crear tabla si no existe
cursor.execute("""
CREATE TABLE IF NOT EXISTS clasificaciones (
    codigo TEXT PRIMARY KEY,
    clasificacion TEXT,
    revisado_por TEXT,
    tiempo_estimado INTEGER
)
""")

conn.commit()
conn.close()

print("✅ Base de datos creada.")
