# utils/error_handler.py
import logging
from flask_mail import Message
from extensions import mail # Asegúrate de que 'mail' esté importado desde extensions.py
from flask import current_app # Necesario para acceder a la configuración de la aplicación

logger = logging.getLogger(__name__)

def enviar_correo_error(asunto, cuerpo):
    """
    Envía un correo electrónico de notificación de error al administrador.
    """
    try:
        # Usar current_app para acceder a la configuración de Flask-Mail
        # Asegúrate de que ADMIN_EMAIL esté configurado en tu config.py
        if not current_app.config.get('ADMIN_EMAIL'):
            logger.warning("ADMIN_EMAIL no está configurado en config.py. No se puede enviar correo de error.")
            print("ADVERTENCIA: ADMIN_EMAIL no está configurado en config.py. No se puede enviar correo de error.")
            return False

        msg = Message(asunto,
                      recipients=[current_app.config['ADMIN_EMAIL']],
                      sender=current_app.config['MAIL_USERNAME'])
        msg.body = cuerpo
        mail.send(msg)
        logger.info(f"Correo de error '{asunto}' enviado al administrador.")
        return True
    except Exception as e:
        logger.error(f"Error crítico al intentar enviar correo de error: {e}", exc_info=True)
        print(f"ERROR CRÍTICO: No se pudo enviar el correo de error. Detalles: {e}")
        return False
