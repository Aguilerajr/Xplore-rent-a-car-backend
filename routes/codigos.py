from fastapi import APIRouter, Request, Form, Depends
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
    x, y = 50, 750

    for codigo in codigos_list:
        img_buffer = io.BytesIO()
        barcode.get("code128", codigo, writer=ImageWriter()).write(img_buffer)
        img_buffer.seek(0)
        c.drawImage(ImageReader(img_buffer), x, y, width=200, height=60)
        c.drawString(x, y - 15, codigo)
        y -= 100
        if y < 100:
            c.showPage()
            y = 750

    c.save()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=codigos.pdf"}
    )
