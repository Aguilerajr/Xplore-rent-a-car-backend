# Configuración de correo para reportes automáticos
import os

def configurar_credenciales_correo():
    """Configura las credenciales de correo para envío automático de reportes"""
    os.environ['EMAIL_USER'] = 'reportexplorerentacar@gmail.com'
    os.environ['EMAIL_PASSWORD'] = 'skjj aceh alqw khpy'
    os.environ['EMAIL_SMTP_SERVER'] = 'smtp.gmail.com'
    os.environ['EMAIL_SMTP_PORT'] = '587'
