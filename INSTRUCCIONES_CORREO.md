# Configuración de Correo Electrónico para Reportes

## Pasos para configurar el envío automático de reportes por correo:

### 1. Configurar Gmail para envío de correos

1. Ve a tu cuenta de Gmail (la que quieres usar para enviar los reportes)
2. Ve a "Gestionar tu cuenta de Google"
3. En el menú izquierdo, selecciona "Seguridad"
4. Busca "Verificación en 2 pasos" y actívala si no está activada
5. Una vez activada la verificación en 2 pasos, busca "Contraseñas de aplicaciones"
6. Genera una nueva contraseña de aplicación:
   - Selecciona "Correo" como aplicación
   - Selecciona "Otro" como dispositivo y escribe "Sistema Reportes"
   - Google te dará una contraseña de 16 caracteres (ejemplo: abcd efgh ijkl mnop)

### 2. Configurar las credenciales en el archivo .env

Abre el archivo `backend1/.env` y reemplaza:

```
EMAIL_USER=tu_correo@gmail.com
EMAIL_PASSWORD=tu_app_password_de_gmail
```

Por:

```
EMAIL_USER=tu_correo_real@gmail.com
EMAIL_PASSWORD=la_contraseña_de_16_caracteres_que_te_dio_google
```

**Ejemplo:**
```
EMAIL_USER=miempresa@gmail.com
EMAIL_PASSWORD=abcd efgh ijkl mnop
```

### 3. ¡Listo!

Una vez configurado, cuando presiones el botón "Generar Reporte":
- ✅ El reporte se descargará en tu computadora (como siempre)
- ✅ El reporte se enviará automáticamente a aguilerajr2004@gmail.com

### Notas importantes:
- Usa la contraseña de aplicación, NO tu contraseña normal de Gmail
- Mantén el archivo .env seguro y no lo compartas
- Si cambias la contraseña de Gmail, tendrás que generar una nueva contraseña de aplicación

### Solución de problemas:
- Si no funciona, verifica que la verificación en 2 pasos esté activada
- Asegúrate de usar la contraseña de aplicación correcta
- Verifica que el correo esté escrito correctamente en EMAIL_USER
