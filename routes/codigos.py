from fastapi import APIRouter, Request, Form, Depends, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import Vehiculo
import io
import barcode
from barcode.writer import ImageWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/crear_codigos", response_class=HTMLResponse)
def crear_codigos(request: Request, db: Session = Depends(get_db)):
    codigos = db.query(Vehiculo.codigo).all()
    return templates.TemplateResponse("crear_codigos.html", {"request": request, "codigos": [c[0] for c in codigos]})

@router.post("/crear_codigos/generar")
def generar_codigos_pdf_o_png(codigos: str = Form(...)):
    codigos_list = [c.strip() for c in codigos.split(",") if c.strip()]
    if not codigos_list:
        return JSONResponse(content={"error": "No se ingresaron códigos válidos."}, status_code=400)

    if len(codigos_list) == 1:
        codigo = codigos_list[0]
        img_buffer = io.BytesIO()
        barcode.get("code128", codigo, writer=ImageWriter()).write(img_buffer)
        img_buffer.seek(0)
        return StreamingResponse(
            img_buffer,
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename={codigo}.png"}
        )

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    x, y = 30, 720
    ancho_codigo = 150
    alto_codigo = 40
    margen_x = 20
    margen_y = 40
    codigos_por_fila = 3

    for idx, codigo in enumerate(codigos_list):
        col = idx % codigos_por_fila
        row = idx // codigos_por_fila
        pos_x = x + col * (ancho_codigo + margen_x)
        pos_y = y - (row % 8) * (alto_codigo + margen_y)

        img_buffer = io.BytesIO()
        barcode.get("code128", codigo, writer=ImageWriter()).write(img_buffer)
        img_buffer.seek(0)
        c.drawImage(ImageReader(img_buffer), pos_x, pos_y, width=ancho_codigo, height=alto_codigo)
        c.setFont("Helvetica", 8)
        c.drawCentredString(pos_x + ancho_codigo / 2, pos_y - 10, codigo)

        if (row + 1) % 8 == 0 and col == codigos_por_fila - 1:
            c.showPage()

    c.save()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=codigos_todos.pdf"}
    )

@router.get("/crear_codigos/generar_todos")
def generar_todos(db: Session = Depends(get_db)):
    codigos = db.query(Vehiculo.codigo).all()
    codigos_list = [c[0] for c in codigos]

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    x, y = 30, 720
    ancho_codigo = 150
    alto_codigo = 40
    margen_x = 20
    margen_y = 40
    codigos_por_fila = 3

    for idx, codigo in enumerate(codigos_list):
        col = idx % codigos_por_fila
        row = idx // codigos_por_fila
        pos_x = x + col * (ancho_codigo + margen_x)
        pos_y = y - (row % 8) * (alto_codigo + margen_y)

        img_buffer = io.BytesIO()
        barcode.get("code128", codigo, writer=ImageWriter()).write(img_buffer)
        img_buffer.seek(0)
        c.drawImage(ImageReader(img_buffer), pos_x, pos_y, width=ancho_codigo, height=alto_codigo)
        c.setFont("Helvetica", 8)
        c.drawCentredString(pos_x + ancho_codigo / 2, pos_y - 10, codigo)

        if (row + 1) % 8 == 0 and col == codigos_por_fila - 1:
            c.showPage()

    c.save()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=codigos_todos.pdf"}
    )

@router.get("/buscar_codigos")
def buscar_codigos(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    resultados = db.query(Vehiculo.codigo).filter(Vehiculo.codigo.ilike(f"%{q}%")).limit(10).all()
    codigos = [codigo[0] for codigo in resultados]
    return {"resultados": codigos}
