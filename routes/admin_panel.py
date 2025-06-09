<!DOCTYPE html>
<html>
<head>
    <title>Login Admin</title>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f4;
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
            margin: 10px 0;
            width: 100%;
        }
        input[type="submit"] {
            background-color: #0066b2;
            color: white;
            font-weight: bold;
            border: none;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <form method="post">
        <h2>Acceso Administrador</h2>
        <input type="password" name="clave" placeholder="Contraseña" required>
        <input type="submit" value="Ingresar">
        {% if error %}
            <p style="color: red;">{{ error }}</p>
        {% endif %}
    </form>
</body>
</html>
