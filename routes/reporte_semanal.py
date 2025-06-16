from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, get_db_empleados
from models import RegistroLavado, Empleado
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
    db: Session = Depends(get_db),
    db_empleados: Session = Depends(get_db_empleados)
):
    try:
        fecha_inicio = datetime.strptime(semana, "%Y-%m-%d")
    except ValueError:
        return templates.TemplateResponse("reporte.html", {"request": request, "error": "Formato de fecha inválido"})

    if fecha_inicio.weekday() != 0:
        return templates.TemplateResponse("reporte.html", {"request": request, "error": "Debes seleccionar un día lunes"})

    numero_semana = fecha_inicio.isocalendar().week
    fecha_fin = fecha_inicio + timedelta(days=6)

    registros = db.query(RegistroLavado).filter(
        RegistroLavado.inicio >= fecha_inicio,
        RegistroLavado.inicio <= fecha_fin
    ).all()

    empleados_todos = [e.nombre for e in db_empleados.query(Empleado).all()]

    # ✅ AGREGADO: hora de inicio y hora de fin en la tabla detalle
    data = []
    for r in registros:
        eficiencia = round((r.tiempo_estimado / r.tiempo_real), 4) if r.tiempo_real else 0
        data.append({
            "Fecha": r.inicio.strftime("%Y-%m-%d"),
            "Hora Inicio": r.inicio.strftime("%H:%M:%S") if r.inicio else "",
            "Hora Fin": r.fin.strftime("%H:%M:%S") if r.fin else "",
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

    resumen["Eficiencia Semanal (%)"] = (
        (resumen["Minutos Estimados"] / resumen["Minutos Reales"])
        .replace([float('inf'), float('nan')], 0)
        .round(4)
    )

    # Asegurar que todos los empleados aparezcan
    resumen = pd.merge(
        pd.DataFrame({"Empleado": empleados_todos}),
        resumen,
        on="Empleado",
        how="left"
    ).fillna({
        "Vehículos Lavados": 0,
        "Minutos Estimados": 0,
        "Minutos Reales": 0,
        "Eficiencia Semanal (%)": 0
    })

    # Gráfico estilo empresarial
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(resumen["Empleado"], resumen["Eficiencia Semanal (%)"] * 100)
    ax.set_title("Eficiencia Diaria", fontsize=14, weight="bold")
    ax.set_ylabel("Eficiencia (%)")
    ax.set_ylim(0, max(100, (resumen["Eficiencia Semanal (%)"] * 100).max() + 10))
    plt.xticks(rotation=45, ha='right')

    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.0f}%', xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom')

    img_data = BytesIO()
    plt.tight_layout()
    plt.savefig(img_data, format='png')
    img_data.seek(0)

    # Crear Excel con formato empresarial
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name="Lavados Detalle", index=False)
        resumen.to_excel(writer, sheet_name="Resumen Semanal", index=False)

        wb = writer.book
        detalle_ws = writer.sheets["Lavados Detalle"]
        resumen_ws = writer.sheets["Resumen Semanal"]

        header_fmt = wb.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'fg_color': '#0066b2', 'color': 'white', 'border': 1
        })
        cell_fmt = wb.add_format({'border': 1, 'align': 'center'})
        pct_fmt = wb.add_format({'num_format': '0.00%', 'border': 1, 'align': 'center'})

        for i, col in enumerate(df.columns):
            detalle_ws.write(0, i, col, header_fmt)
            detalle_ws.set_column(i, i, 20)

        for i, col in enumerate(resumen.columns):
            resumen_ws.write(0, i, col, header_fmt)
            resumen_ws.set_column(i, i, 22)
            fmt = pct_fmt if "Eficiencia" in col else cell_fmt
            for row in range(len(resumen)):
                resumen_ws.write(row + 1, i, resumen.iloc[row, i], fmt)

        resumen_ws.insert_image("H2", "grafico.png", {"image_data": img_data})

    output.seek(0)
    nombre_archivo = f"reporte_semanal_semana_{numero_semana}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"}
    )
