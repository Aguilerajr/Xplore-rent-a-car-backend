from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

# Contraseña maestra (puedes cambiarla)
CLAVE_ACCESO = "admin123"

# Nombre de la cookie de sesión
NOMBRE_COOKIE = "acceso_autorizado"

def verificar_acceso(request: Request) -> bool:
    """
    Verifica si el usuario tiene acceso autorizado mediante cookie.
    """
    return request.cookies.get(NOMBRE_COOKIE) == "true"

def obtener_login_response() -> str:
    """
    Retorna un formulario de login en HTML simple como string.
    """
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login</title>
        <meta charset="utf-8">
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f5f5f5;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }
            form {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }
            input {
                padding: 10px;
                width: 100%;
                margin: 10px 0;
                border-radius: 5px;
                border: 1px solid #ccc;
            }
            input[type="submit"] {
                background-color: #0066b2;
                color: white;
                cursor: pointer;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <form method="post">
            <h2>Acceso restringido</h2>
            <input type="password" name="clave" placeholder="Contraseña">
            <input type="submit" value="Ingresar">
        </form>
    </body>
    </html>
    """

def ruta_login(router, ruta="/login"):
    """
    Crea una ruta de login básica que verifica la clave y establece una cookie de sesión.
    """
    @router.get(ruta, response_class=HTMLResponse)
    def mostrar_login():
        return HTMLResponse(content=obtener_login_response())

    @router.post(ruta, response_class=HTMLResponse)
    def procesar_login(clave: str = ""):
        if clave == CLAVE_ACCESO:
            response = RedirectResponse("/", status_code=302)
            response.set_cookie(key=NOMBRE_COOKIE, value="true", httponly=True)
            return response
        return HTMLResponse(content=obtener_login_response())
