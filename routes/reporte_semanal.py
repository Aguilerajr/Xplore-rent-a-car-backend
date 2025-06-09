from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import RegistroLavado
from io import BytesIO
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/reporte_semanal")
def formulario_reporte(request: Request):
    return templates.TemplateResponse("reporte.html", {"request": request, "error": None})

@router.post("/reporte_semanal")
def generar_reporte(
    request: Request,
    semana: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        fecha_inicio = datetime.strptime(semana, "%Y-%m-%d")
    except ValueError:
        return templates.TemplateResponse("reporte.html", {"request": request, "error": "Formato de fecha inválido"}, status_code=400)

    if fecha_inicio.weekday() != 0:
        return templates.TemplateResponse("reporte.html", {"request": request, "error": "Debes seleccionar un día lunes"}, status_code=400)

    numero_semana = fecha_inicio.isocalendar().week
    fecha_fin = fecha_inicio + timedelta(days=6)

    registros = db.query(RegistroLavado).filter(
        RegistroLavado.inicio >= fecha_inicio,
        RegistroLavado.inicio <= fecha_fin
    ).all()

    if not registros:
        return templates.TemplateResponse("reporte.html", {"request": request, "error": "No hay registros para esa semana"}, status_code=404)

    data = []
    for r in registros:
        eficiencia = round((r.tiempo_estimado / r.tiempo_real) * 100, 2) if r.tiempo_real else 0
        data.append({
            "Fecha": r.inicio.strftime("%Y-%m-%d"),
            "Empleado": r.nombre_empleado,
            "Vehículo": r.vehiculo,
            "Minutos Estimados": r.tiempo_estimado,
            "Minutos Reales": r.tiempo_real,
            "Eficiencia (%)": eficiencia
        })

    df = pd.DataFrame(data)

    resumen = df.groupby("Empleado").agg({
        "Vehículo": "count",
        "Minutos Estimados": "sum",
        "Minutos Reales": "sum"
    }).reset_index()
    resumen.rename(columns={"Vehículo": "Vehículos Lavados"}, inplace=True)
    resumen["Eficiencia Semanal (%)"] = round(
        (resumen["Minutos Estimados"] / resumen["Minutos Reales"]).replace([float('inf'), float('nan')], 0) * 100, 2
    )

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(resumen["Empleado"], resumen["Eficiencia Semanal (%)"])
    ax.set_title("Eficiencia Diaria", fontsize=14, weight="bold")
    ax.set_ylabel("Porcentaje", fontsize=12)
    ax.set_ylim(0, 100)
    ax.set_xticklabels(resumen["Empleado"], rotation=45, ha='right')
    plt.tight_layout()

    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.0f}%', xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom')

    img_data = BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name="Lavados Detalle", index=False)
        resumen.to_excel(writer, sheet_name="Resumen Semanal", index=False)
        worksheet = writer.sheets["Resumen Semanal"]
        worksheet.insert_image("H2", "grafico.png", {"image_data": img_data})

    output.seek(0)
    nombre_archivo = f"reporte_semanal_semana_{numero_semana}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"}
    )
