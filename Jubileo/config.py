# C:\Jubileo\config.py

import os

class Config:
 
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f"mysql+pymysql://{os.environ.get('DB_USER', 'root')}:{os.environ.get('DB_PASSWORD', '')}@" \
        f"{os.environ.get('DB_HOST', 'localhost')}:{os.environ.get('DB_PORT', '3306')}/{os.environ.get('DB_NAME', 'jubileo')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configuración de Flask-Mail para envío de correos
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'notificaciones.jubileoazul@gmail.com' # ¡CAMBIAR POR TU CORREO!
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'dkwq hvhy bqkb ktzi' # ¡CAMBIAR POR TU CONTRASEÑA DE APLICACIÓN!
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'notificaciones.jubileoazul@gmail.com' # ¡CAMBIAR POR TU CORREO!
    # En tu archivo config.py
    ADMIN_EMAIL = '23300101@uttt.edu.mx'
    
    # Clave secreta para la seguridad de la sesión de Flask
    # ¡GENERAR UNA CLAVE MUY LARGA Y COMPLEJA PARA PRODUCCIÓN!
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'una_clave_secreta_muy_dificil_de_adivinar_y_larga_para_desarrollo'

    # Configuración de Flask-APScheduler
    SCHEDULER_API_ENABLED = True
