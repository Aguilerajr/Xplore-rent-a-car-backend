from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from models import RegistroLavado
from io import BytesIO
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

router = APIRouter()

@router.get("/reporte_semanal")
def generar_reporte_excel(
    semana: str = Query(..., description="Fecha del lunes de la semana (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    try:
        fecha_inicio = datetime.strptime(semana, "%Y-%m-%d")
    except ValueError:
        return JSONResponse(content={"detalle": "Formato de fecha inválido. Usa YYYY-MM-DD"}, status_code=400)

    fecha_fin = fecha_inicio + timedelta(days=6)

    # Consultar base de datos
    registros = db.query(RegistroLavado).filter(
        RegistroLavado.fecha >= fecha_inicio,
        RegistroLavado.fecha <= fecha_fin
    ).all()

    if not registros:
        return JSONResponse(content={"detalle": "No hay registros para esa semana"}, status_code=404)

    # Crear DataFrame
    data = []
    for r in registros:
        eficiencia = round((r.minutos_estimados / r.minutos_reales) * 100, 2) if r.minutos_reales else 0
        data.append({
            "Fecha": r.fecha.strftime("%Y-%m-%d"),
            "Empleado": r.nombre_empleado,
            "Vehículo": r.codigo_vehiculo,
            "Minutos Estimados": r.minutos_estimados,
            "Minutos Reales": r.minutos_reales,
            "Eficiencia (%)": eficiencia
        })

    df = pd.DataFrame(data)

    # Resumen por empleado
    resumen = df.groupby("Empleado").agg({
        "Vehículo": "count",
        "Minutos Estimados": "sum",
        "Minutos Reales": "sum"
    }).reset_index()
    resumen.rename(columns={"Vehículo": "Vehículos Lavados"}, inplace=True)
    resumen["Eficiencia Semanal (%)"] = round(
        (resumen["Minutos Estimados"] / resumen["Minutos Reales"]) * 100, 2
    )

    # Crear gráfico
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(resumen["Empleado"], resumen["Eficiencia Semanal (%)"])
    ax.set_title("Eficiencia Semanal por Empleado")
    ax.set_ylabel("Eficiencia (%)")
    ax.set_ylim(0, 120)
    plt.tight_layout()

    img_data = BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)

    # Crear archivo Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name="Detalle", index=False)
        resumen.to_excel(writer, sheet_name="Resumen", index=False)
        worksheet = writer.sheets["Resumen"]
        worksheet.insert_image("G2", "grafico.png", {"image_data": img_data})

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=reporte_semanal.xlsx"}
    )
