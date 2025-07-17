# C:\Jubileo\app.py

import sys
import traceback
import logging
import os
from datetime import datetime, timedelta
from collections import defaultdict # Necesario para defaultdict en verificar_vencimientos

from flask import Flask, render_template, redirect, url_for, flash, request, send_file, current_app 
from flask_login import login_required, current_user 
from flask_mail import Message 
from sqlalchemy import func 

from extensions import db, mail, scheduler, login_manager

# --- Configuración del logger al inicio del archivo ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Cambiado a DEBUG para ver logs detallados
logger = logging.getLogger(__name__)
# ----------------------------------------------------

# Ajusta el sys.path para asegurar que las importaciones de modelos funcionen correctamente
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'models'))) 

try:
    # Importa las clases de los modelos directamente desde sus módulos
    from models.usuario import Usuario 
    from models.cliente import Cliente
    from models.condicion_comodato import CondicionesComodato 
    
    logger.debug(f"DEBUG: 'Usuario' importado exitosamente desde: {Usuario.__module__}")
    logger.debug(f"DEBUG: Ubicación de Usuario: {Usuario}")
    logger.debug(f"DEBUG: Tiene 'check_password': {'check_password' in dir(Usuario)}")
    logger.debug(f"DEBUG: Tiene 'is_active': {'is_active' in dir(Usuario)}")
except ImportError as e:
    logger.error(f"ERROR: No se pudo importar un modelo. Detalles: {e}")
    logger.debug(f"DEBUG: sys.path: {sys.path}")

# Importa las funciones auxiliares desde el nuevo archivo utils/pdf_helpers.py
from utils.pdf_helpers import _agregar_articulos_comodato, _render_pdf_template_for_email

from routes.auth import auth_bp
from routes.clientes import clientes_bp
from routes.comodatos import comodatos_bp
from routes.usuarios import usuarios_bp
from routes.main import main_bp 

from config import Config
from utils.error_handler import enviar_correo_error

from weasyprint import HTML, CSS
import io 


app = None # Variable global para la instancia de la aplicación Flask

def enviar_correo_vencimiento(destinatario, asunto, cuerpo, pdf_bytes=None, filename=None):
    """
    Envía un correo electrónico de notificación de vencimiento.
    Esta función debe ser llamada dentro de un contexto de aplicación.
    """
    if app is None:
        logger.error("La aplicación Flask no está inicializada. No se puede enviar el correo.")
        return False

    with app.app_context(): # Asegura que estamos en un contexto de aplicación para acceder a 'app.config' y 'mail'
        try:
            msg = Message(asunto, recipients=[destinatario], sender=app.config['MAIL_USERNAME'])
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
    """
    Verifica los comodatos próximos a vencer y envía correos de notificación al cliente y al encargado.
    Esta función se ejecuta como una tarea programada.
    """
    if app is None:
        logger.error("La aplicación Flask no está inicializada. No se puede verificar vencimientos.")
        return

    with app.app_context(): # Asegura que estamos en un contexto de aplicación para acceder a 'db'
        hoy = datetime.now().date()
        fecha_limite = hoy + timedelta(days=7) # Comodatos que vencen en los próximos 7 días
        logger.info(f"Verificando vencimientos. Hoy: {hoy}, Fecha límite: {fecha_limite}")

        try:
            all_candidate_comodatos = db.session.query(CondicionesComodato).filter(
                CondicionesComodato.fechaDevolucion <= fecha_limite,
                CondicionesComodato.notificado_vencimiento == 0 
            ).all()

            comodatos_agrupados_por_cliente_y_fecha = defaultdict(list) 
            for comodato_rec in all_candidate_comodatos:
                if comodato_rec.NoFolio and comodato_rec.fechaDevolucion:
                    key = (comodato_rec.NoFolio, comodato_rec.fechaDevolucion)
                    comodatos_agrupados_por_cliente_y_fecha[key].append(comodato_rec)
                else:
                    logger.warning(f"Comodato {comodato_rec.idComodato} omitido: Falta NoFolio o fechaDevolucion.")

            logger.info(f"Se encontraron {len(all_candidate_comodatos)} comodatos candidatos. Agrupados en {len(comodatos_agrupados_por_cliente_y_fecha)} grupos.")

            for (no_folio, fecha_devolucion_grupo), raw_comodato_items_for_group in comodatos_agrupados_por_cliente_y_fecha.items():
                try:
                    cliente = Cliente.query.get(no_folio)
                    if not cliente:
                        logger.error(f"Cliente con NoFolio {no_folio} no encontrado para la agrupación de comodatos.")
                        continue 

                    main_comodato_ref = raw_comodato_items_for_group[0] # Tomamos el primer comodato del grupo como referencia

                    # --- Agrupar artículos idénticos ---
                    comodato_items_aggregated_for_output = _agregar_articulos_comodato(raw_comodato_items_for_group)
                    # DEBUGGING: Log los items agregados antes de pasar al template
                    logger.info(f"DEBUG_EMAIL_RENDER: Items passed to EMAIL template for client {no_folio}, date {fecha_devolucion_grupo}: {comodato_items_aggregated_for_output}")

                    # --- CALCULAR IMPORTE TOTAL AQUI EN PYTHON ---
                    total_importe_para_email = sum(item['importe'] for item in comodato_items_aggregated_for_output)
                    logger.debug(f"DEBUG_EMAIL_RENDER: Calculated total_importe_para_email: {total_importe_para_email:.2f}")

                    # Generar el PDF personalizado para esta agrupación
                    rendered_html_pdf = _render_pdf_template_for_email(
                        cliente_obj=cliente, # cliente_obj ya contiene NoCliente
                        comodato_items_list=comodato_items_aggregated_for_output, # Usamos la lista agregada para el PDF
                        main_comodato_ref_obj=main_comodato_ref,
                        total_importe_para_email=total_importe_para_email # Pasamos el total ya calculado
                    )
                    pdf_bytes_generated = HTML(string=rendered_html_pdf, base_url=current_app.root_path).write_pdf()
                    pdf_filename = f'Nota_Comodato_{cliente.nombreComercial.replace(" ", "_")}_{cliente.NoFolio}_FD_{fecha_devolucion_grupo.strftime("%Y%m%d")}.pdf'

                    # --- Correo para el Cliente ---
                    asunto_cliente = f"Recordatorio de Vencimiento de Comodato(s) - {cliente.nombreComercial}"
                    cuerpo_cliente = f"""
Estimado/a {cliente.nombreComercial},

Este es un recordatorio de que su(s) comodato(s) está(n) próximo(s) a vencer.

Concepto(s): {[item['concepto'] for item in comodato_items_aggregated_for_output]} 
Fecha de Devolución: {fecha_devolucion_grupo.strftime('%d/%m/%Y')}

Por favor, revise el archivo adjunto (nota de comodato) para realizar la firma de la renovacion del comodato o 
en dado caso su cancelación, le pedimos por favor realice la firma del comodato (digital o escrita), 
y pueda responder este correo con el archivo firmado

Atentamente,
El Sistema Gestor de Jubileo Azul
"""
                    destinatario_cliente = cliente.email
                    if destinatario_cliente:
                        if enviar_correo_vencimiento(destinatario_cliente, asunto_cliente, cuerpo_cliente, pdf_bytes_generated, pdf_filename):
                            for item in raw_comodato_items_for_group: # Marcar los ítems RAW como notificados
                                item.notificado_vencimiento = 1
                            db.session.commit()
                            logger.info(f"Vencimiento de comodatos para cliente {no_folio}, fecha {fecha_devolucion_grupo} notificado al cliente y marcado en DB.")
                        else:
                            logger.error(f"No se pudo enviar el correo de vencimiento al cliente para la agrupación de comodatos {no_folio}, fecha {fecha_devolucion_grupo}.")
                    else:
                        logger.warning(f"No se pudo enviar correo de vencimiento al cliente para la agrupación {no_folio}, fecha {fecha_devolucion_grupo}: No hay correo electrónico del cliente.")

                    # --- Correo para el Encargado ---
                    encargado_email = '23300101@uttt.edu.mx' # ¡Reemplaza con el email real del encargado!
                    if encargado_email:
                        asunto_encargado = f"COMODATO Vencimiento Próximo: Cliente {cliente.nombreComercial} - Fecha Dev. {fecha_devolucion_grupo.strftime('%d/%m/%Y')}"
                        
                        articulos_en_agrupacion = ""
                        for item in comodato_items_aggregated_for_output: # Usar la lista agregada para detalles del correo
                            articulos_en_agrupacion += f"""
    - Concepto: {item['concepto']}
      Cantidad: {item['cantidad']} {item['UM'] if item['UM'] else ''}
      Costo Unitario: ${item['costo']:.2f}
      Importe Agregado: ${item['importe']:.2f}
      Importe Total Agregado: ${item['importeTotal']:.2f}
"""
                        # Agregar campos de main_comodato_ref si es necesario para detalles generales del grupo
                        articulos_en_agrupacion += f"""
      Motivo Préstamo: {main_comodato_ref.motivoPrestamo if main_comodato_ref.motivoPrestamo else 'N/A'}
      Folio Sustitución: {main_comodato_ref.folioSustitucion if main_comodato_ref.folioSustitucion else 'N/A'}
"""

                        cuerpo_encargado = f"""Estimada Encargada,

Se ha detectado comodatos próximos a vencer para el cliente {cliente.nombreComercial}.

Detalles de la Agrupación:
    No. Folio Cliente: {cliente.NoFolio}
    No. de Cliente: {cliente.NoCliente if cliente.NoCliente else 'N/A'} 
    Nombre Comercial: {cliente.nombreComercial}
    Fecha de Devolución Agrupada: {fecha_devolucion_grupo.strftime('%d/%m/%Y')}

Artículos en esta Agrupación:
{articulos_en_agrupacion}

Detalles Adicionales del Cliente:
    Tipo de Cliente: {cliente.tipoCliente if cliente.tipoCliente else 'N/A'}
    Teléfono: {cliente.telefono if cliente.telefono else 'N/A'}
    Email del Cliente: {cliente.email if cliente.email else 'No Proporcionado'}
    Dirección: {cliente.calle if cliente.calle else 'N/A'} {cliente.numero if cliente.numero else 'N/A'}, {cliente.colonia if cliente.colonia else 'N/A'}, {cliente.municipio if cliente.municipio else 'N/A'}, {cliente.estado if cliente.estado else 'N/A'}, CP {cliente.cp if cliente.cp else 'N/A'}
    Ruta: {cliente.ruta if cliente.ruta else 'N/A'}
    Fecha de Préstamo: {cliente.fechaPrestamo.strftime('%d/%m/%Y') if cliente.fechaPrestamo else 'N/A'}

Por favor, tome las acciones necesarias.

Atentamente,
Sistema Gestor de Jubileo Azul
"""
                        if enviar_correo_vencimiento(encargado_email, asunto_encargado, cuerpo_encargado):
                            logger.info(f"Vencimiento de comodatos para cliente {no_folio}, fecha {fecha_devolucion_grupo} notificado al encargado {encargado_email}.")
                        else:
                            logger.error(f"No se pudo notificar el vencimiento de comodatos para la agrupación {no_folio}, fecha {fecha_devolucion_grupo} al encargado {encargado_email}.")
                    else:
                        logger.warning("Email del encargado no configurado. No se envió notificación al encargado.")

                except Exception as group_e:
                    logger.error(f"Error procesando agrupación para cliente {no_folio}, fecha {fecha_devolucion_grupo}: {group_e}", exc_info=True)
                    enviar_correo_error(
                        asunto=f"Error en Sistema de Comodatos: Procesando Agrupación {no_folio} - {fecha_devolucion_grupo}",
                        cuerpo=f"Ocurrió un error al procesar la agrupación de comodatos.\n\nDetalles del error: {group_e}"
                    )
            
            db.session.commit() # Commit final después de procesar todas las agrupaciones

        except Exception as e:
            error_message = f"Error al verificar los vencimientos: {e}"
            logger.error(error_message, exc_info=True)
            print(error_message)
            enviar_correo_error(asunto="Error al verificar vencimientos (Global)", cuerpo=error_message)
            db.session.rollback() 


def create_app():
    """
    Crea y configura la aplicación Flask.
    Esta función centraliza la inicialización de la aplicación y sus extensiones.
    """
    global app 
    app = Flask(__name__)
    app.config.from_object(Config) 

    # --- NUEVA LÍNEA DE DEPURACIÓN: Log la URI de la base de datos ---
    logger.info(f"DEBUG_DB: SQLALCHEMY_DATABASE_URI configurada: {app.config['SQLALCHEMY_DATABASE_URI']}")
    # -----------------------------------------------------------------

    db.init_app(app) 
    mail.init_app(app) 
    scheduler.init_app(app) 

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    # Personaliza el mensaje de Flask-Login para la redirección de login_required
    login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
    login_manager.login_message_category = "info" 

    @login_manager.user_loader
    def load_user(user_id):
        with app.app_context():
            return Usuario.query.get(int(user_id))

    app.jinja_env.globals.update(now=datetime.now)

    app.register_blueprint(auth_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(comodatos_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(main_bp) 

    @app.route('/')
    def index():
        return redirect(url_for('auth.login')) 

    return app

if __name__ == '__main__':
    try:
        app = create_app() 
        logger.info("Aplicación Flask inicializada.")

        with app.app_context():
            db.create_all() 
            logger.info("Tablas de la base de datos verificadas/creadas.")

            logger.info("Ejecutando verificación de vencimientos manualmente para prueba...")
            verificar_vencimientos()
            logger.info("Verificación de vencimientos manual completada.")

        scheduler.start()
        scheduler.add_job(id='verificar_vencimientos_job', func=verificar_vencimientos, trigger='interval', hours=24)
        logger.info("Scheduler iniciado y tarea 'verificar_vencimientos_job' añadida.")

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
