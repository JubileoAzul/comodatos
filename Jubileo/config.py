# C:\Jubileo\config.py

import os

class Config:
    # Configuración de la base de datos
    # Lee de DATABASE_URL si está disponible (Render), o construye desde variables individuales
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f"mysql+pymysql://{os.environ.get('DB_USER', 'root')}:{os.environ.get('DB_PASSWORD', '')}@" \
        f"{os.environ.get('DB_HOST', 'localhost')}:{os.environ.get('DB_PORT', '3306')}/{os.environ.get('DB_NAME', 'jubileo')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configuración de Flask-Mail para envío de correos
    # IMPORTANTE: En Render, configura estas variables como 'Environment Variables'
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    # MAIL_USE_TLS y MAIL_USE_SSL deben ser 'True' o 'False' como cadenas en las variables de entorno
    # o None / True en el código para que os.environ.get() funcione con 'is not None'
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true' # Asegura que sea booleano
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true' # Asegura que sea booleano

    # Valores de respaldo para desarrollo local (¡NUNCA pongas contraseñas reales aquí!)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or '' # Tu correo de envío
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or '' # Contraseña de aplicación de Gmail (solo para local si no usas env vars)
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or '' # Correo remitente por defecto

    # Correo del administrador para notificaciones de error
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or '' # Correo del administrador

    # Clave secreta para la seguridad de la sesión de Flask
    # ¡GENERAR UNA CLAVE MUY LARGA Y COMPLEJA PARA PRODUCCIÓN Y CONFIGURARLA EN RENDER!
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'una_clave_secreta_muy_dificil_de_adivinar_y_larga_para_desarrollo'

    # Configuración de Flask-APScheduler
    SCHEDULER_API_ENABLED = True
