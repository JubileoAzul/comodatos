import sys
import traceback
import logging
import os
import threading # Necesario para ejecutar la verificación en segundo plano
from datetime import datetime, timedelta
from collections import defaultdict # ¡NUEVO! Importar para agrupar comodatos

from flask import Flask, render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user
from flask_mail import Message
from sqlalchemy import func

# Eliminamos 'scheduler' de las extensiones, ya no lo necesitamos
from extensions import db, mail, login_manager

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'models')))

try:
    from models.usuario import Usuario
    from models.cliente import Cliente
    from models.condicion_comodato import CondicionesComodato

    print(f"DEBUG: 'Usuario' importado exitosamente desde: {Usuario.__module__}")
    print(f"DEBUG: Ubicación de Usuario: {Usuario}")
    print(f"DEBUG: Tiene 'check_password': {'check_password' in dir(Usuario)}")
    print(f"DEBUG: Tiene 'is_active': {'is_active' in dir(Usuario)}")
except ImportError as e:
    print(f"ERROR: No se pudo importar un modelo. Detalles: {e}")
    print(f"DEBUG: sys.path: {sys.path}")


from routes.auth import auth_bp
from routes.clientes import clientes_bp
from routes.comodatos import comodatos_bp
from routes.usuarios import usuarios_bp
from routes.main import main_bp

from config import Config
from utils.error_handler import enviar_correo_error
from utils.pdf_helpers import _agregar_articulos_comodato # ¡NUEVO! Importar la función de agrupación

from weasyprint import HTML, CSS
import io


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# La variable 'app' se inicializará aquí después de que create_app() sea definida.
# Esto asegura que Gunicorn pueda encontrar la instancia de la aplicación.
app = None # Se declara globalmente pero se inicializa más abajo

# --- Variables globales para la ejecución única de la verificación ---
# Esta bandera asegura que la verificación de vencimientos solo se ejecute una vez
# por cada proceso del servidor (cada vez que la app se despliega o "despierta").
_verification_done_for_this_process = False
# Este candado previene condiciones de carrera si múltiples requests llegan
# simultáneamente justo cuando la app está despertando.
_verification_lock = threading.Lock()


def enviar_correo_vencimiento(destinatario, asunto, cuerpo, pdf_bytes=None, filename=None):
    # Usamos current_app para acceder a la instancia de la aplicación dentro del contexto.
    # Esto es más robusto que usar la variable global 'app' directamente en funciones
    # que se ejecutan en hilos o contextos de request.
    try:
        # Asegúrate de que el contexto de la aplicación esté activo.
        # En este caso, ya lo estará si se llama desde verificar_vencimientos,
        # que a su vez se llama dentro de un app_context().
        msg = Message(asunto, recipients=[destinatario], sender=current_app.config['MAIL_USERNAME'])
        msg.body = cuerpo
        if pdf_bytes and filename:
            try:
                msg.attach(filename, 'application/pdf', pdf_bytes)
                logger.info(f"Archivo {filename} adjuntado con éxito.")
            except Exception as e:
                logger.error(f"Error al adjuntar el archivo PDF {filename}: {e}", exc_info=True)
                print(f"Error al adjuntar el archivo PDF {filename}: {e}")
        mail.send(msg)
        logger.info(f"Correo de vencimiento enviado a {destinatario}")
        print(f"Correo de vencimiento enviado a {destinatario}")
        return True
    except Exception as e:
        logger.error(f"Error al enviar el correo a {destinatario}: {e}", exc_info=True)
        print(f"Error al enviar el correo a {destinatario}: {e}")
        return False

def verificar_vencimientos():
    # La función ahora asume que siempre se llamará dentro de un app_context()
    # como se maneja en el decorador @app.before_request.
    # No necesitamos el `if app is None:` check aquí directamente,
    # ya que el contexto de la app lo manejará.

    hoy = datetime.now().date()
    fecha_limite = hoy + timedelta(days=7)
    logger.info(f"Iniciando ejecución de verificar_vencimientos. Hoy: {hoy}, Fecha límite: {fecha_limite}")

    try:
        # Obtener todos los comodatos que necesitan notificación y sus clientes asociados
        # No filtramos por 'notificado_vencimiento' aquí inicialmente para poder agrupar
        # y luego marcar en el bucle de envío.
        raw_comodatos_a_notificar = db.session.query(CondicionesComodato, Cliente).join(
            Cliente, CondicionesComodato.NoFolio == Cliente.NoFolio
        ).filter(
            CondicionesComodato.fechaDevolucion <= fecha_limite
        ).all()

        logger.info(f"Se encontraron {len(raw_comodatos_a_notificar)} comodatos para posible notificación (antes de agrupar y filtrar por notificado).")

        # Diccionario para agrupar comodatos por (NoFolio del cliente, fechaDevolucion)
        # Cada entrada contendrá una lista de tuplas (CondicionesComodato, Cliente)
        comodatos_agrupados = defaultdict(list)

        for comodato_obj, cliente_obj in raw_comodatos_a_notificar:
            # Solo consideramos para notificación aquellos que aún no han sido notificados
            if comodato_obj.notificado_vencimiento == 0:
                key = (comodato_obj.NoFolio, comodato_obj.fechaDevolucion)
                comodatos_agrupados[key].append((comodato_obj, cliente_obj))

        logger.info(f"Se formaron {len(comodatos_agrupados)} grupos de comodatos a notificar.")

        for (no_folio, fecha_devolucion_grupo), comodato_cliente_pairs in comodatos_agrupados.items():
            # Tomamos el primer comodato y cliente del grupo para obtener los datos principales
            # y el objeto cliente para el PDF y el correo.
            main_comodato_obj = comodato_cliente_pairs[0][0] # Primer comodato del grupo
            cliente_obj = comodato_cliente_pairs[0][1] # Cliente asociado a ese comodato

            # Agrupar los ítems del comodato usando la función auxiliar
            # Pasamos solo los objetos comodato a la función de agregación
            comodato_items_aggregated = _agregar_articulos_comodato([c[0] for c in comodato_cliente_pairs])

            # Calcular el importe total del grupo de comodatos agregados
            final_grand_total = sum(item['importe'] for item in comodato_items_aggregated)
            logger.debug(f"DEBUG_VERIFICACION: Calculated final_grand_total for group {no_folio}/{fecha_devolucion_grupo}: {final_grand_total:.2f}")

            datos_empresa = {
                'nombre_empresa': 'Jubileo Azul S.A. de C.V.',
                'rfc_empresa': 'JAZ990101XYZ',
                'direccion_empresa': 'AV. CRUZ AZUL S/N COL. CENTRO, CD. COOPERATIVA CRUZ AZUL, TULA DE ALLENDE, HGO. C.P. 42840',
                'telefono_empresa': '(S) 01 (773) 785 1962 / 785 2231',
                'email_empresa': 'pampajubileo@googlegroups.net',
            }

            # Renderizar la plantilla HTML para el PDF
            rendered_html_pdf = render_template(
                'pdf_templates/comodato_note.html',
                main_comodato_ref=main_comodato_obj, # ¡Ahora pasamos la variable con el nombre esperado!
                cliente=cliente_obj,
                comodato_items=comodato_items_aggregated, # Pasamos la lista de ítems agregados para la tabla
                grand_total_importe=final_grand_total, # Pasamos el total calculado
                datos_empresa=datos_empresa
            )

            # current_app.root_path es necesario para que WeasyPrint encuentre los recursos CSS/imágenes locales
            pdf_bytes_generated = HTML(string=rendered_html_pdf, base_url=current_app.root_path).write_pdf()
            pdf_filename = f'Nota_Comodato_{cliente_obj.nombreComercial.replace(" ", "_")}_{cliente_obj.NoFolio}_FD_{fecha_devolucion_grupo.strftime("%Y%m%d")}.pdf'

            asunto_cliente = f"Recordatorio de Vencimiento de Comodato - {cliente_obj.nombreComercial}"
            cuerpo_cliente = f"""
Estimado/a {cliente_obj.nombreComercial},

Este es un recordatorio de que uno o varios de sus comodatos están próximos a vencer.
La fecha de devolución para este grupo de artículos es: {fecha_devolucion_grupo.strftime('%d/%m/%Y')}

Por favor, revise el archivo adjunto (Nota de Comodato) para obtener más información sobre los artículos específicos.

Atentamente,
El equipo de Jubileo Azul
"""
            destinatario_cliente = cliente_obj.email
            if destinatario_cliente:
                if enviar_correo_vencimiento(destinatario_cliente, asunto_cliente, cuerpo_cliente, pdf_bytes_generated, pdf_filename):
                    # Marcar TODOS los comodatos de este grupo como notificados
                    for comodato_to_update, _ in comodato_cliente_pairs:
                        comodato_to_update.notificado_vencimiento = 1
                    db.session.commit()
                    logger.info(f"Vencimientos para cliente {cliente_obj.NoFolio} (fecha {fecha_devolucion_grupo}) notificados y marcados en DB.")
                else:
                    logger.error(f"No se pudo enviar el correo de vencimiento al cliente {cliente_obj.NoFolio} para el grupo de comodatos.")
            else:
                logger.warning(f"No se pudo enviar correo de vencimiento al cliente {cliente_obj.NoFolio} para el grupo de comodatos: No hay correo electrónico del cliente.")

            encargado_email = current_app.config.get('ADMIN_EMAIL')
            if encargado_email:
                asunto_encargado = f"[ENCARGADO] Vencimiento Próximo (Grupo): Cliente {cliente_obj.NoFolio} - {cliente_obj.nombreComercial}"
                cuerpo_encargado = f"""
Estimado Encargado,

Se ha detectado un grupo de comodatos próximos a vencer o ya vencidos para el cliente {cliente_obj.nombreComercial} (No. Folio: {cliente_obj.NoFolio}).
La fecha de devolución para este grupo es: {fecha_devolucion_grupo.strftime('%d/%m/%Y')}

Por favor, revise el archivo adjunto (Nota de Comodato) para obtener los detalles de los artículos.

Atentamente,
Sistema de Gestión de Comodatos
"""
                if enviar_correo_vencimiento(encargado_email, asunto_encargado, cuerpo_encargado, pdf_bytes_generated, pdf_filename):
                    logger.info(f"Vencimiento de grupo de comodatos para cliente {cliente_obj.NoFolio} notificado al encargado {encargado_email}.")
                else:
                    logger.error(f"No se pudo notificar el vencimiento del grupo de comodatos para cliente {cliente_obj.NoFolio} al encargado {encargado_email}.")
            else:
                logger.warning("Email del encargado no configurado. No se envió notificación al encargado.")

        logger.info("Ejecución de verificar_vencimientos completada.")

    except Exception as e:
        error_message = f"Error al verificar los vencimientos: {e}"
        logger.error(error_message, exc_info=True)
        print(error_message)
        enviar_correo_error(asunto="Error al verificar vencimientos", cuerpo=error_message)
        db.session.rollback()


# Define una función auxiliar para ejecutar la verificación en un hilo separado
def _run_verification_in_background(app_instance):
    """
    Ejecuta la función verificar_vencimientos dentro del contexto de la aplicación.
    Esto asegura que las extensiones de Flask (como db y mail) sean accesibles.
    """
    with app_instance.app_context():
        try:
            logger.info("Iniciando ejecución de verificar_vencimientos en el hilo de fondo.")
            verificar_vencimientos()
            logger.info("Verificación de vencimientos en el hilo de fondo completada.")
        except Exception as e:
            # Captura cualquier error que ocurra dentro de verificar_vencimientos
            # y lo loguea, además de intentar enviar un correo de error.
            error_message = f"Error crítico en el hilo de verificación de vencimientos: {e}"
            logger.error(error_message, exc_info=True)
            # Intenta enviar un correo de error si la app está disponible
            try:
                enviar_correo_error(asunto="Error en verificación de vencimientos en segundo plano", cuerpo=error_message)
            except Exception as mail_e:
                logger.error(f"No se pudo enviar correo de error de verificación en segundo plano: {mail_e}", exc_info=True)


def create_app():
    global app
    _app = Flask(__name__) # Usa una variable local para la instancia de Flask
    _app.config.from_object(Config)

    db.init_app(_app)
    mail.init_app(_app)
    # scheduler.init_app(_app) # ¡ELIMINADO! Ya no necesitamos el scheduler

    login_manager.init_app(_app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
    login_manager.login_message_category = "info"

    # Mover db.create_all() aquí para que se ejecute en producción
    with _app.app_context():
        db.create_all()
        logger.info("Tablas de la base de datos verificadas/creadas en el contexto de la aplicación.")

    @login_manager.user_loader
    def load_user(user_id):
        with _app.app_context(): # Usa _app aquí también
            return Usuario.query.get(int(user_id))

    _app.jinja_env.globals.update(now=datetime.now)

    _app.register_blueprint(auth_bp)
    _app.register_blueprint(clientes_bp)
    _app.register_blueprint(comodatos_bp)
    _app.register_blueprint(usuarios_bp)
    _app.register_blueprint(main_bp)

    # --- HOOK PARA EJECUTAR VERIFICACIÓN EN EL PRIMER REQUEST ---
    @_app.before_request
    def run_verification_on_startup():
        global _verification_done_for_this_process
        global _verification_lock # Asegúrate de acceder a la global

        with _verification_lock:
            if not _verification_done_for_this_process:
                logger.info("Primer request recibido. Iniciando verificación de vencimientos en segundo plano...")
                # Inicia el hilo, pasando la instancia de la aplicación (_app)
                threading.Thread(target=_run_verification_in_background, args=(_app,)).start()
                _verification_done_for_this_process = True
                logger.info("Verificación de vencimientos iniciada. La aplicación responderá normalmente.")

    @_app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    return _app

# Asigna la instancia de la aplicación a la variable global 'app' aquí
# Esto asegura que 'app' esté disponible cuando Gunicorn importe el módulo.
app = create_app()

if __name__ == '__main__':
    # Este bloque solo se ejecuta cuando corres 'python app.py' directamente
    try:
        logger.info("Aplicación Flask inicializada.")

        # Eliminamos las líneas relacionadas con el scheduler y la ejecución manual
        # de verificar_vencimientos aquí, ya que el @before_request lo manejará.

        app.run(debug=True, host='0.0.0.0', port=5000)

    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
        error_message = f"Ocurrió un error crítico durante la inicialización/ejecución de la aplicación:\n\nDetalles del error:\n{''.join(traceback_details)}"
        logger.critical(error_message, exc_info=True)

        if app:
            with app.app_context():
                enviar_correo_error(asunto="Error crítico de inicio de la aplicación Jubileo", cuerpo=error_message)
        else:
            print(f"Error crítico: La aplicación no se pudo inicializar. No se puede enviar correo de error. Detalles: {error_message}")
        print(f"\n¡La aplicación no pudo iniciarse!\n{error_message}")
