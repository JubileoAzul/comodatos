import sys
import traceback
import logging
import os
import threading #Necesario para ejecutar la verificación en segundo plano
from datetime import datetime, timedelta

from flask import Flask, render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user
from flask_mail import Message
from sqlalchemy import func


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
        comodatos_a_notificar_query = db.session.query(
            CondicionesComodato.idComodato,
            Cliente.NoFolio,
            Cliente.nombreComercial,
            Cliente.telefono,
            Cliente.email,
            Cliente.fechaPrestamo,
            Cliente.tipoCliente,
            Cliente.ruta,
            Cliente.calle,
            Cliente.numero,
            Cliente.colonia,
            Cliente.municipio,
            Cliente.estado,
            Cliente.cp,
            CondicionesComodato.concepto,
            CondicionesComodato.fechaDevolucion,
            CondicionesComodato.motivoPrestamo,
            CondicionesComodato.otroMotivo,
            CondicionesComodato.folioSustitucion,
            CondicionesComodato.cantidad,
            CondicionesComodato.UM,
            CondicionesComodato.costo,
            CondicionesComodato.importe,
            CondicionesComodato.importeTotal
        ).join(Cliente, CondicionesComodato.NoFolio == Cliente.NoFolio).filter(
            CondicionesComodato.fechaDevolucion <= fecha_limite,
            CondicionesComodato.notificado_vencimiento == 0
        ).all()

        logger.info(f"Se encontraron {len(comodatos_a_notificar_query)} comodatos para notificar.")

        for comodato_data in comodatos_a_notificar_query:

            comodato_para_pdf = CondicionesComodato(
                idComodato=comodato_data.idComodato,
                NoFolio=comodato_data.NoFolio,
                fechaDevolucion=comodato_data.fechaDevolucion,
                concepto=comodato_data.concepto,
                cantidad=comodato_data.cantidad,
                UM=comodato_data.UM,
                costo=comodato_data.costo,
                importe=comodato_data.importe,
                importeTotal=comodato_data.importeTotal,
                motivoPrestamo=comodato_data.motivoPrestamo,
                otroMotivo=comodato_data.otroMotivo,
                folioSustitucion=comodato_data.folioSustitucion
            )
            cliente_para_pdf = Cliente(
                NoFolio=comodato_data.NoFolio,
                nombreComercial=comodato_data.nombreComercial,
                tipoCliente=comodato_data.tipoCliente,
                fechaPrestamo=comodato_data.fechaPrestamo,
                ruta=comodato_data.ruta,
                telefono=comodato_data.telefono,
                email=comodato_data.email,
                calle=comodato_data.calle,
                numero=comodato_data.numero,
                colonia=comodato_data.colonia,
                municipio=comodato_data.municipio,
                estado=comodato_data.estado,
                cp=comodato_data.cp
            )

            datos_empresa = {
                'nombre_empresa': 'Jubileo Azul S.A. de C.V.',
                'rfc_empresa': 'JAZ990101XYZ',
                'direccion_empresa': 'AV. CRUZ AZUL S/N COL. CENTRO, CD. COOPERATIVA CRUZ AZUL, TULA DE ALLENDE, HGO. C.P. 42840',
                'telefono_empresa': '(S) 01 (773) 785 1962 / 785 2231',
                'email_empresa': 'pampajubileo@googlegroups.net',
            }

            rendered_html_pdf = render_template(
                'pdf_templates/comodato_note.html',
                comodato=comodato_para_pdf,
                cliente=cliente_para_pdf,
                datos_empresa=datos_empresa
            )

            # current_app.root_path es necesario para que WeasyPrint encuentre los recursos CSS/imágenes locales
            pdf_bytes_generated = HTML(string=rendered_html_pdf, base_url=current_app.root_path).write_pdf()
            pdf_filename = f'Nota_Comodato_{comodato_data.nombreComercial}_{comodato_data.NoFolio}_{comodato_data.idComodato}.pdf'

            asunto_cliente = f"Recordatorio de Vencimiento de Comodato - {comodato_data.concepto}"
            cuerpo_cliente = f"""
Estimado/a {comodato_data.nombreComercial},

Este es un recordatorio de que su comodato del siguiente artículo está próximo a vencer:

Concepto: {comodato_data.concepto}
Fecha de Devolución: {comodato_data.fechaDevolucion.strftime('%d/%m/%Y')}

Por favor, revise el archivo adjunto (Nota de Comodato) para obtener más información sobre los siguientes pasos.

Atentamente,
El equipo de Jubileo Azul
"""
            destinatario_cliente = comodato_data.email
            if destinatario_cliente:
                if enviar_correo_vencimiento(destinatario_cliente, asunto_cliente, cuerpo_cliente, pdf_bytes_generated, pdf_filename):
                    comodato_a_actualizar = CondicionesComodato.query.get(comodato_data.idComodato)
                    if comodato_a_actualizar:
                        comodato_a_actualizar.notificado_vencimiento = 1
                        db.session.commit()
                        logger.info(f"Vencimiento de comodato {comodato_data.idComodato} notificado al cliente y marcado en DB.")
                    else:
                        logger.warning(f"Comodato {comodato_data.idComodato} no encontrado para actualizar notificación después de enviar al cliente.")
                else:
                    logger.error(f"No se pudo enviar el correo de vencimiento al cliente para el comodato {comodato_data.idComodato}.")
            else:
                logger.warning(f"No se pudo enviar correo de vencimiento al cliente para el comodato {comodato_data.idComodato}: No hay correo electrónico del cliente.")

            encargado_email = current_app.config.get('ADMIN_EMAIL') # Usar current_app.config.get para leer ADMIN_EMAIL
            if encargado_email:
                asunto_encargado = f"[ENCARGADO] Vencimiento Próximo: Comodato ID {comodato_data.idComodato} - {comodato_data.concepto}"
                cuerpo_encargado = f"""
Estimado Encargado,

Se ha detectado un comodato próximo a vencer o ya vencido que requiere su atención.

Detalles del Comodato:
    ID Comodato: {comodato_data.idComodato}
    Concepto: {comodato_data.concepto}
    Motivo del Préstamo: {comodato_data.motivoPrestamo if comodato_data.motivoPrestamo else 'N/A'}
    Fecha de Devolución: {comodato_data.fechaDevolucion.strftime('%d/%m/%Y')}
    Cantidad: {comodato_data.cantidad if comodato_data.cantidad is not None else 'N/A'} {comodato_data.UM if comodato_data.UM else 'N/A'}
    Importe Total: ${comodato_data.importeTotal if comodato_data.importeTotal is not None else 'N/A'}

Detalles del Cliente:
    No. Folio Cliente: {comodato_data.NoFolio}
    Nombre Comercial: {comodato_data.nombreComercial}
    Tipo de Cliente: {comodato_data.tipoCliente if comodato_data.tipoCliente else 'N/A'}
    Teléfono: {comodato_data.telefono if comodato_data.telefono else 'N/A'}
    Email del Cliente: {comodato_data.email if comodato_data.email else 'No Proporcionado'}
    Dirección: {comodato_data.calle if comodato_data.calle else 'N/A'} {comodato_data.numero if comodato_data.numero else 'N/A'}, {comodato_data.colonia if comodato_data.colonia else 'N/A'}, {comodato_data.municipio if comodato_data.municipio else 'N/A'}, {comodato_data.estado if comodato_data.estado else 'N/A'}, CP {comodato_data.cp if comodato_data.cp else 'N/A'}
    Ruta: {comodato_data.ruta if comodato_data.ruta else 'N/A'}
    Fecha de Préstamo (Cliente): {comodato_data.fechaPrestamo.strftime('%d/%m/%Y') if comodato_data.fechaPrestamo else 'N/A'}

Por favor, tome las acciones necesarias.

Atentamente,
Sistema de Gestión de Comodatos
"""
                if enviar_correo_vencimiento(encargado_email, asunto_encargado, cuerpo_encargado):
                    logger.info(f"Vencimiento de comodato {comodato_data.idComodato} notificado al encargado {encargado_email}.")
                else:
                    logger.error(f"No se pudo notificar el vencimiento del comodato {comodato_data.idComodato} al encargado {encargado_email}.")
            else:
                logger.warning("Email del encargado no configurado. No se envió notificación al encargado.")

        logger.info("Ejecución de verificar_vencimientos completada.")

    except Exception as e:
        error_message = f"Error al verificar los vencimientos: {e}"
        logger.error(error_message, exc_info=True)
        print(error_message)
        enviar_correo_error(asunto="Error al verificar vencimientos", cuerpo=error_message)
        db.session.rollback()


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

        # Usamos un candado para asegurar que solo un hilo intente ejecutar la verificación
        # si múltiples solicitudes llegan al mismo tiempo en el inicio.
        with _verification_lock:
            if not _verification_done_for_this_process:
                logger.info("Primer request recibido. Iniciando verificación de vencimientos en segundo plano...")
                # Ejecutamos verificar_vencimientos en un hilo separado para no bloquear
                # la respuesta al primer usuario que accede a la aplicación.
                # Es crucial pasar el contexto de la aplicación al hilo si verificar_vencimientos
                # necesita acceder a la configuración de la app o a la base de datos.
                # La sintaxis `lambda: _app.app_context().push() or verificar_vencimientos() or _app.app_context().pop()`
                # asegura que el contexto de la app esté disponible dentro del hilo.
                # Usamos _app porque estamos dentro de la función create_app()
                threading.Thread(target=lambda: _app.app_context().push() or verificar_vencimientos() or _app.app_context().pop()).start()
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
