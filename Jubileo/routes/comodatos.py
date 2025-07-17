import io
import logging
from datetime import datetime, timedelta 
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app 
from flask_login import login_required, current_user
from sqlalchemy import func, or_ 
from collections import defaultdict 

from weasyprint import HTML, CSS 

from extensions import db 
from models.cliente import Cliente 
from models.condicion_comodato import CondicionesComodato 
from models.usuario import Usuario 

from utils.error_handler import enviar_correo_error
# Importa la función auxiliar desde el nuevo archivo
# Asegúrate de que utils/pdf_helpers.py exista y contenga _agregar_articulos_comodato
from utils.pdf_helpers import _agregar_articulos_comodato 

logger = logging.getLogger(__name__)

comodatos_bp = Blueprint('comodatos', __name__, url_prefix='/comodatos')

@comodatos_bp.route('/')
def index_comodatos():
    """Ruta principal para la gestión de comodatos."""
    return redirect(url_for('comodatos.listar_comodatos'))


@comodatos_bp.route('/listar', methods=['GET'])
@login_required
def listar_comodatos():
    """
    Ruta para mostrar la lista de todos los comodatos junto con la información de sus clientes.
    Permite filtrar por palabra clave y rangos de fecha.
    Requiere que el usuario esté logueado.
    """
    search_query = request.args.get('query', '').strip()
    fecha_prestamo_search_str = request.args.get('fecha_prestamo_search', '').strip()
    fecha_devolucion_search_str = request.args.get('fecha_devolucion_search', '').strip()

    logger.debug(f"DEBUG_FILTER_INPUT: search_query='{search_query}', fecha_prestamo_search_str='{fecha_prestamo_search_str}', fecha_devolucion_search_str='{fecha_devolucion_search_str}'")

    try:
        # Construir la consulta base
        query = db.session.query(CondicionesComodato, Cliente).join(
            Cliente, CondicionesComodato.NoFolio == Cliente.NoFolio
        )

        # Determinar si se están aplicando filtros
        applying_filters = bool(search_query or fecha_prestamo_search_str or fecha_devolucion_search_str)

        # Aplicar filtros condicionalmente
        if search_query:
            search_pattern = f"%{search_query}%"
            query = query.filter(
                or_(
                    Cliente.nombreComercial.ilike(search_pattern),
                    Cliente.telefono.ilike(search_pattern),
                    Cliente.email.ilike(search_pattern),
                    Cliente.calle.ilike(search_pattern),
                    Cliente.colonia.ilike(search_pattern),
                    Cliente.municipio.ilike(search_pattern),
                    Cliente.estado.ilike(search_pattern),
                    Cliente.cp.ilike(search_pattern),
                    CondicionesComodato.concepto.ilike(search_pattern),
                    CondicionesComodato.motivoPrestamo.ilike(search_pattern),
                    CondicionesComodato.otroMotivo.ilike(search_pattern),
                    CondicionesComodato.folioSustitucion.ilike(search_pattern),
                    func.cast(CondicionesComodato.idComodato, db.String).ilike(search_pattern),
                    func.cast(Cliente.NoFolio, db.String).ilike(search_pattern),
                    func.cast(Cliente.NoCliente, db.String).ilike(search_pattern) # Filtrar por NoCliente
                )
            )

        if fecha_prestamo_search_str:
            try:
                # Filtra para fechas exactamente iguales a la fecha seleccionada
                fecha_prestamo_search = datetime.strptime(fecha_prestamo_search_str, '%Y-%m-%d').date()
                logger.debug(f"DEBUG_FILTER_PARSE: Parsed fecha_prestamo_search: {fecha_prestamo_search} (Type: {type(fecha_prestamo_search)})")
                query = query.filter(Cliente.fechaPrestamo == fecha_prestamo_search) 
                logger.debug(f"DEBUG_FILTER_APPLY: Applied fechaPrestamo filter: == {fecha_prestamo_search}")
            except ValueError:
                flash("Formato de Fecha de Préstamo inválido. Usa: AAAA-MM-DD.", 'error')
                logger.warning(f"DEBUG_FILTER_ERROR: Invalid Fecha de Préstamo format: {fecha_prestamo_search_str}")


        if fecha_devolucion_search_str:
            try:
                # Filtra para fechas exactamente iguales a la fecha seleccionada
                fecha_devolucion_search = datetime.strptime(fecha_devolucion_search_str, '%Y-%m-%d').date()
                logger.debug(f"DEBUG_FILTER_PARSE: Parsed fecha_devolucion_search: {fecha_devolucion_search} (Type: {type(fecha_devolucion_search)})")
                query = query.filter(CondicionesComodato.fechaDevolucion == fecha_devolucion_search) 
                logger.debug(f"DEBUG_FILTER_APPLY: Applied fechaDevolucion filter: == {fecha_devolucion_search}")
            except ValueError:
                flash("Formato de Fecha de Devolución inválido. Usa: AAAA-MM-DD.", 'error')
                logger.warning(f"DEBUG_FILTER_ERROR: Invalid Fecha de Devolución format: {fecha_devolucion_search_str}")

        # Aplicar orden y límite solo si NO se están aplicando filtros
        if not applying_filters:
            query = query.order_by(CondicionesComodato.idComodato.desc()).limit(10)
            logger.info("DEBUG_INITIAL_LOAD: Mostrando los 10 comodatos más recientes.")
        else:
            logger.info("DEBUG_FILTERED_LOAD: Mostrando todos los comodatos que coinciden con los filtros.")

        comodatos_con_clientes = query.all()

        logger.info(f"Se encontraron {len(comodatos_con_clientes)} comodatos después de filtrar.")

        lista_comodatos = []
        for comodato_rec, cliente_rec in comodatos_con_clientes: 
            logger.debug(f"DEBUG_RESULT_ITEM: Comodato ID: {comodato_rec.idComodato}, Cliente Fecha Préstamo (DB): {cliente_rec.fechaPrestamo} (Type: {type(cliente_rec.fechaPrestamo)}), Comodato Fecha Devolución (DB): {comodato_rec.fechaDevolucion} (Type: {type(comodato_rec.fechaDevolucion)})")
            lista_comodatos.append({
                'idComodato': comodato_rec.idComodato,
                'NoFolioCliente': cliente_rec.NoFolio,
                'NoCliente': cliente_rec.NoCliente, # Incluir NoCliente en la lista
                'nombreComercialCliente': cliente_rec.nombreComercial,
                'tipoCliente': cliente_rec.tipoCliente,
                # Formatear la fecha para la visualización en la tabla (DD/MM/YYYY)
                'fechaPrestamo': cliente_rec.fechaPrestamo.strftime('%d/%m/%Y') if cliente_rec.fechaPrestamo else 'N/A', 
                'ruta': cliente_rec.ruta if cliente_rec.ruta else 'N/A',
                'telefono': cliente_rec.telefono if cliente_rec.telefono else 'N/A',
                'email': cliente_rec.email if cliente_rec.email else 'N/A', 
                'calle': cliente_rec.calle if cliente_rec.calle else 'N/A',
                'numero': cliente_rec.numero if cliente_rec.numero else 'N/A',
                'colonia': cliente_rec.colonia if cliente_rec.colonia else 'N/A',
                'municipio': cliente_rec.municipio if cliente_rec.municipio else 'N/A',
                'estado': cliente_rec.estado if cliente_rec.estado else 'N/A', 
                'cp': cliente_rec.cp if cliente_rec.cp else 'N/A',
                'motivoPrestamo': comodato_rec.motivoPrestamo if comodato_rec.motivoPrestamo else 'N/A',
                'otroMotivo': comodato_rec.otroMotivo if comodato_rec.otroMotivo else 'N/A',
                # Formatear la fecha para la visualización en la tabla (DD/MM/YYYY)
                'fechaDevolucion': comodato_rec.fechaDevolucion.strftime('%d/%m/%Y') if comodato_rec.fechaDevolucion else 'N/A', 
                'folioSustitucion': comodato_rec.folioSustitucion if comodato_rec.folioSustitucion else 'N/A',
                'cantidad': comodato_rec.cantidad if comodato_rec.cantidad is not None else 'N/A',
                'UM': comodato_rec.UM if comodato_rec.UM else 'N/A',
                'concepto': comodato_rec.concepto if comodato_rec.concepto else 'N/A',
                'costo': comodato_rec.costo if comodato_rec.costo is not None else 'N/A',
                'importe': comodato_rec.importe if comodato_rec.importe is not None else 'N/A',
                'importeTotal': comodato_rec.importeTotal if comodato_rec.importeTotal is not None else 'N/A',
            })
        
        return render_template(
            'comodatos/listar.html', 
            comodatos=lista_comodatos,
            search_query=search_query,
            fecha_prestamo_search=fecha_prestamo_search_str, # Pasar la cadena original para pre-llenar el input type="date"
            fecha_devolucion_search=fecha_devolucion_search_str # Pasar la cadena original para pre-llenar el input type="date"
        )

    except Exception as e:
        error_msg = f'Error al listar comodatos: {e}'
        logger.error(error_msg, exc_info=True)
        enviar_correo_error(
            asunto="Error en Sistema de Comodatos: Listado de Comodatos",
            cuerpo=f"Ha ocurrido un error inesperado al intentar listar los comodatos.\n\nDetalles del error: {error_msg}"
        )
        flash('Ocurrió un error al cargar la lista de comodatos.', 'error')
        return redirect(url_for('main.index'))


# --- Ruta para agregar un nuevo comodato ---
@comodatos_bp.route('/agregar', methods=['GET', 'POST'])
@login_required
def agregar_comodato():
    """
    Ruta para agregar un nuevo comodato y, si es necesario, un nuevo cliente.
    Maneja tanto la visualización del formulario (GET) como el procesamiento (POST).
    """
    if request.method == 'POST':
        # --- INICIALIZACIÓN DE VARIABLES PARA EVITAR EL ERROR 'UNBOUNDLOCALERROR' ---
        no_folio_cliente = None 
        cliente = None
        # -------------------------------------------------------------------------
        try:
            # Obtener datos del formulario para Cliente
            no_folio_cliente_str = request.form.get('NoFolio')
            if not no_folio_cliente_str:
                raise ValueError("El campo 'No. Folio Cliente' es requerido.")
            no_folio_cliente = int(no_folio_cliente_str) 

            no_cliente_from_form = request.form.get('NoCliente') # OBTENER EL NUEVO CAMPO NoCliente

            nombre_comercial = request.form.get('nombreComercial')
            if not nombre_comercial:
                raise ValueError("El campo 'Nombre Comercial' es requerido.")
            
            tipo_cliente = request.form.get('tipoCliente')
            ruta = request.form.get('ruta')
            telefono = request.form.get('telefono')
            email = request.form.get('email')
            calle = request.form.get('calle')
            numero = request.form.get('numero')
            colonia = request.form.get('colonia')
            municipio = request.form.get('municipio')
            estado = request.form.get('estado')
            cp = request.form.get('cp')

            # Obtener datos del formulario para CondicionComodato
            fecha_prestamo_str = request.form.get('fechaPrestamo') 
            fecha_devolucion_str = request.form.get('fechaDevolucion')
            concepto = request.form.get('concepto')
            cantidad_str = request.form.get('cantidad')
            um = request.form.get('UM')
            costo_str = request.form.get('costo')
            importe_str = request.form.get('importe')
            importe_total_str = request.form.get('importeTotal')
            
            motivo_prestamo = request.form.get('motivoPrestamo') 
            logger.debug(f"DEBUG_ADD: Motivo de Préstamo recibido del formulario: '{motivo_prestamo}'") 
            
            otro_motivo = request.form.get('otroMotivo')
            folio_sustitucion = request.form.get('folioSustitucion')

            # Validaciones y conversiones
            if not fecha_devolucion_str or not concepto or not cantidad_str or not costo_str or not importe_str or not importe_total_str or not motivo_prestamo:
                raise ValueError("Por favor, complete todos los campos obligatorios del comodato (Concepto, Cantidad, Costo, Importe, Importe Total, Motivo de Préstamo y Fecha de Devolución).")
            
            # Asegurar la conversión a float, limpiando posibles caracteres no numéricos
            try:
                cantidad = int(cantidad_str)
                costo = float(str(costo_str).replace('$', '').replace(',', ''))
                importe = float(str(importe_str).replace('$', '').replace(',', ''))
                importe_total = float(str(importe_total_str).replace('$', '').replace(',', ''))
            except (ValueError, TypeError) as e:
                raise ValueError(f"Error al convertir valor numérico: {e}. Verifique formato de Costo, Importe o Importe Total.")


            # Convertir fechas de string a objeto datetime.date
            fecha_prestamo_cliente = None
            if fecha_prestamo_str:
                fecha_prestamo_cliente = datetime.strptime(fecha_prestamo_str, '%Y-%m-%d').date()
            
            fecha_devolucion = datetime.strptime(fecha_devolucion_str, '%Y-%m-%d').date()

            # Verificar si el cliente ya existe por su NoFolio
            cliente_existente = Cliente.query.get(no_folio_cliente)
            if cliente_existente:
                flash(f'El cliente con No. Folio {no_folio_cliente} ya existe. Se asociará el comodato a este cliente y se actualizarán sus datos.', 'info')
                cliente = cliente_existente
                # Actualizar los datos del cliente existente
                cliente.nombreComercial = nombre_comercial
                cliente.tipoCliente = tipo_cliente
                cliente.ruta = ruta
                cliente.telefono = telefono
                cliente.email = email
                cliente.calle = calle
                cliente.numero = numero
                cliente.colonia = colonia
                cliente.municipio = municipio
                cliente.estado = estado
                cliente.cp = cp
                cliente.fechaPrestamo = fecha_prestamo_cliente
                cliente.NoCliente = no_cliente_from_form # ACTUALIZAR NoCliente para cliente existente
            else:
                # Si el cliente no existe, crear uno nuevo
                nuevo_cliente = Cliente(
                    NoFolio=no_folio_cliente,
                    NoCliente=no_cliente_from_form, # ASIGNAR NoCliente para nuevo cliente
                    nombreComercial=nombre_comercial,
                    tipoCliente=tipo_cliente,
                    fechaPrestamo=fecha_prestamo_cliente,
                    ruta=ruta,
                    telefono=telefono,
                    email=email,
                    calle=calle,
                    numero=numero,
                    colonia=colonia,
                    municipio=municipio,
                    estado=estado,
                    cp=cp
                )
                db.session.add(nuevo_cliente)
                cliente = nuevo_cliente

            # Crear nuevo comodato, relacionándolo con el cliente
            nuevo_comodato = CondicionesComodato( 
                NoFolio=no_folio_cliente, 
                fechaDevolucion=fecha_devolucion,
                concepto=concepto,
                cantidad=cantidad,
                UM=um,
                costo=costo,
                importe=importe,
                importeTotal=importe_total,
                motivoPrestamo=motivo_prestamo, 
                otroMotivo=otro_motivo,
                folioSustitucion=folio_sustitucion,
            )
            logger.debug(f"DEBUG_ADD: Motivo de Préstamo a guardar en la DB: '{nuevo_comodato.motivoPrestamo}'") 
            db.session.add(nuevo_comodato)
            db.session.commit()
            flash('Comodato agregado exitosamente.', 'success')
            return redirect(url_for('comodatos.listar_comodatos'))

        except ValueError as ve:
            db.session.rollback()
            error_msg = f"Error de validación al agregar comodato: {ve}"
            logger.error(error_msg, exc_info=True)
            flash(f'Error en el formato de los datos: {ve}', 'error')
        except Exception as e:
            db.session.rollback()
            error_msg = f"Error inesperado al agregar comodato: {e}"
            logger.error(error_msg, exc_info=True)
            enviar_correo_error(
                asunto="Error en Sistema de Comodatos: Agregar Comodato",
                cuerpo=f"Ha ocurrido un error inesperado al intentar agregar un comodato.\n\nDetalles del error: {error_msg}"
            )
            flash(f'Ocurrió un error al agregar el comodato: {e}', 'error')

    no_folio_cliente_pre = request.args.get('NoFolio')
    clientes = Cliente.query.all()
    form = {} 
    return render_template('comodatos/agregar.html', no_folio_cliente_pre=no_folio_cliente_pre, clientes=clientes, form=form)


# --- Ruta para editar un comodato existente ---
@comodatos_bp.route('/editar/<int:idComodato>', methods=['GET', 'POST'])
@login_required
def editar_comodato(idComodato):
    """
    Ruta para editar un comodato existente.
    Carga el comodato y su cliente asociado para la edición.
    """
    comodato = CondicionesComodato.query.get_or_404(idComodato) 
    cliente = Cliente.query.get_or_404(comodato.NoFolio)

    if request.method == 'POST':
        try:
            # Actualizar datos del Cliente con la información del formulario
            cliente.nombreComercial = request.form['nombreComercial']
            cliente.tipoCliente = request.form['tipoCliente']
            cliente.ruta = request.form.get('ruta')
            cliente.telefono = request.form.get('telefono')
            cliente.email = request.form.get('email')
            cliente.calle = request.form.get('calle')
            cliente.numero = request.form.get('numero')
            cliente.colonia = request.form.get('colonia')
            cliente.municipio = request.form.get('municipio')
            cliente.estado = request.form.get('estado')
            cliente.cp = request.form.get('cp')
            cliente.NoCliente = request.form.get('NoCliente') # ACTUALIZAR NoCliente para cliente existente
            
            fecha_prestamo_cliente_str = request.form.get('fechaPrestamo')
            if fecha_prestamo_cliente_str:
                cliente.fechaPrestamo = datetime.strptime(fecha_prestamo_cliente_str, '%Y-%m-%d').date()
            else:
                cliente.fechaPrestamo = None

            # Actualizar datos de CondicionesComodato con la información del formulario
            comodato.fechaDevolucion = datetime.strptime(request.form['fechaDevolucion'], '%Y-%m-%d').date()
            comodato.concepto = request.form['concepto']
            comodato.cantidad = int(request.form['cantidad'])
            
            # Asegurar la conversión a float, limpiando posibles caracteres no numéricos
            try:
                comodato.costo = float(str(request.form['costo']).replace('$', '').replace(',', ''))
                comodato.importe = float(str(request.form['importe']).replace('$', '').replace(',', ''))
                comodato.importeTotal = float(str(request.form['importeTotal']).replace('$', '').replace(',', ''))
            except (ValueError, TypeError) as e:
                raise ValueError(f"Error al convertir valor numérico en edición: {e}. Verifique formato de Costo, Importe o Importe Total.")
            
            comodato.UM = request.form.get('UM')
            
            motivo_prestamo_from_form = request.form.get('motivoPrestamo')
            logger.debug(f"DEBUG_EDIT: Motivo de Préstamo recibido del formulario: '{motivo_prestamo_from_form}'") 
            comodato.motivoPrestamo = motivo_prestamo_from_form 
            logger.debug(f"DEBUG_EDIT: Motivo de Préstamo a guardar en la DB para comodato ID {idComodato}: '{comodato.motivoPrestamo}'") 

            comodato.otroMotivo = request.form.get('otroMotivo')
            comodato.folioSustitucion = request.form.get('folioSustitucion')

            db.session.commit()
            flash('Comodato actualizado exitosamente.', 'success')
            return redirect(url_for('comodatos.listar_comodatos'))

        except ValueError as ve:
            db.session.rollback()
            error_msg = f"Error de validación al editar comodato ID {idComodato}: {ve}"
            logger.error(error_msg, exc_info=True)
            flash(f'Error en el formato de los datos: {ve}', 'error')
        except Exception as e:
            db.session.rollback()
            error_msg = f"Error inesperado al editar comodato ID {idComodato}: {e}"
            logger.error(error_msg, exc_info=True)
            enviar_correo_error(
                asunto="Error en Sistema de Comodatos: Editar Comodato",
                cuerpo=f"Ha ocurrido un error inesperado al intentar editar el comodato con ID: {idComodato}.\n\nDetalles del error: {error_msg}"
            )
            flash(f'Ocurrió un error al editar el comodato: {e}', 'error')
    
    return render_template(
        'comodatos/editar.html',
        comodato=comodato,
        cliente=cliente,
        form={} 
    )


# --- Nueva ruta para eliminar un comodato (AGREGADA) ---
@comodatos_bp.route('/eliminar/<int:idComodato>', methods=['POST'])
@login_required
def eliminar_comodato(idComodato):
    """
    Ruta para eliminar un comodato existente.
    """
    logger.info(f"Intento de eliminación para comodato ID: {idComodato}")
    try:
        comodato = CondicionesComodato.query.get_or_404(idComodato)
        logger.info(f"Comodato encontrado para eliminación: {comodato.idComodato}")
        db.session.delete(comodato)
        logger.info(f"Comodato {comodato.idComodato} marcado para eliminación. Intentando commit...")
        db.session.commit()
        logger.info(f"Comodato {idComodato} eliminado exitosamente y cambios confirmados en la DB.")
        flash('Comodato eliminado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        error_msg = f"Error al eliminar comodato ID {idComodato}: {e}"
        logger.error(error_msg, exc_info=True) # Asegura que la traza completa se registre
        enviar_correo_error(
            asunto="Error en Sistema de Comodatos: Eliminar Comodato",
            cuerpo=f"Ha ocurrido un error inesperado al intentar eliminar el comodato con ID: {idComodato}.\n\nDetalles del error: {error_msg}"
        )
        flash(f'Ocurrió un error al eliminar el comodato: {e}', 'error')
    return redirect(url_for('comodatos.listar_comodatos'))


# --- NUEVA RUTA: Renovar Comodato ---
@comodatos_bp.route('/renovar/<int:idComodato>', methods=['POST'])
@login_required
def renovar_comodato(idComodato):
    """
    Renueva un comodato específico:
    - Adelanta la fecha de devolución un año.
    - Resetea el flag notificado_vencimiento a 0 para permitir futuras notificaciones.
    """
    try:
        comodato = CondicionesComodato.query.get_or_404(idComodato)

        if comodato.fechaDevolucion:
            # Adelantar la fecha de devolución un año
            # Manejo de años bisiestos: si es 29 de febrero, irá al 28 de febrero del siguiente año
            try:
                comodato.fechaDevolucion = comodato.fechaDevolucion.replace(year=comodato.fechaDevolucion.year + 1)
            except ValueError:
                # Si es 29 de febrero y el siguiente año no es bisiesto, ajusta al 28 de febrero
                comodato.fechaDevolucion = comodato.fechaDevolucion.replace(month=2, day=28, year=comodato.fechaDevolucion.year + 1)
            
            # Resetea el flag de notificación
            comodato.notificado_vencimiento = 0
            
            db.session.commit()
            flash(f'Comodato ID {idComodato} renovado exitosamente. Nueva fecha de devolución: {comodato.fechaDevolucion.strftime("%d/%m/%Y")}.', 'success')
        else:
            flash('No se puede renovar el comodato: la fecha de devolución no está definida.', 'error')

    except Exception as e:
        db.session.rollback()
        error_msg = f"Error al renovar comodato ID {idComodato}: {e}"
        logger.error(error_msg, exc_info=True)
        enviar_correo_error(
            asunto="Error en Sistema de Comodatos: Renovar Comodato",
            cuerpo=f"Ha ocurrido un error inesperado al intentar renovar el comodato con ID: {idComodato}.\n\nDetalles del error: {error_msg}"
        )
        flash(f'Ocurrió un error al renovar el comodato: {e}', 'error')
    
    return redirect(url_for('comodatos.editar_comodato', idComodato=idComodato))


# --- Nueva ruta para generar la nota de comodato en PDF (AGRUPADA) ---
@comodatos_bp.route('/generar_nota_comodato/<int:idComodato>')
@login_required 
def generar_nota_comodato(idComodato):
    """
    Genera una nota de comodato en formato PDF para un comodato específico,
    agrupando otros comodatos del mismo cliente con la misma fecha de devolución.
    Los artículos idénticos (mismo concepto y U.M.) se sumarán en cantidad e importe.
    """
    try:
        # 1. Obtener el comodato principal para extraer NoFolio y fechaDevolucion
        main_comodato = CondicionesComodato.query.get_or_404(idComodato)
        
        if not main_comodato.fechaDevolucion:
            flash('El comodato seleccionado no tiene una fecha de devolución definida y no se puede generar una nota agrupada.', 'error')
            return redirect(url_for('comodatos.listar_comodatos'))

        no_folio = main_comodato.NoFolio
        fecha_devolucion_grupo = main_comodato.fechaDevolucion

        # 2. Obtener el cliente asociado
        cliente = Cliente.query.get_or_404(no_folio)

        # 3. Obtener TODOS los comodatos de ese cliente con la MISMA fecha de devolución
        raw_comodato_items = CondicionesComodato.query.filter_by(
            NoFolio=no_folio,
            fechaDevolucion=fecha_devolucion_grupo
        ).all()

        if not raw_comodato_items:
            flash('No se encontraron comodatos para agrupar bajo este cliente y fecha de devolución.', 'error')
            logger.warning(f"Intento de generar nota agrupada para cliente {no_folio} y fecha {fecha_devolucion_grupo} sin comodatos.")
            return redirect(url_for('comodatos.listar_comodatos'))

        # --- Agrupar artículos idénticos ---
        # Ahora se usa la nueva función auxiliar para procesar los items
        comodato_items_aggregated = _agregar_articulos_comodato(raw_comodato_items)
        # DEBUGGING: Log los items agregados antes de pasar al template
        logger.info(f"DEBUG_PDF_RENDER: Items passed to PDF template: {comodato_items_aggregated}")
        
        # --- CALCULAR IMPORTE TOTAL AQUI EN PYTHON ---
        final_grand_total = sum(item['importe'] for item in comodato_items_aggregated)
        logger.debug(f"DEBUG_PDF_RENDER: Calculated final_grand_total: {final_grand_total:.2f}")

        logger.debug(f"DEBUG_PDF_RENDER: Valor de main_comodato_ref.motivoPrestamo: '{main_comodato.motivoPrestamo}'")


        datos_empresa = {
            'nombre_empresa': 'Jubileo Azul S.A. de C.V.',
            'rfc_empresa': 'JAZ990101XYZ', 
            'direccion_empresa': 'AV. CRUZ AZUL S/N COL. CENTRO, CD. COOPERATIVA CRUZ AZUL, TULA DE ALLENDE, HGO. C.P. 42840', 
            'telefono_empresa': '(S) 01 (773) 785 1962 / 785 2231', 
            'email_empresa': 'pampajubileo@googlegroups.net', 
        }

        # Renderizar la plantilla HTML para el PDF, pasando la lista de comodatos AGREGADOS
        rendered_html = render_template(
            'pdf_templates/comodato_note.html',
            cliente=cliente, 
            comodato_items=comodato_items_aggregated, # ¡Ahora es la lista agregada!
            datos_empresa=datos_empresa,
            main_comodato_ref=main_comodato,
            grand_total_importe=final_grand_total # Pasamos el total ya calculado
        )

        pdf_bytes = HTML(string=rendered_html, base_url=request.url_root).write_pdf()

        download_name=f'Nota_Comodato_{cliente.nombreComercial.replace(" ", "_")}_{cliente.NoFolio}_FD_{fecha_devolucion_grupo.strftime("%Y%m%d")}.pdf'
        
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True, 
            download_name=download_name 
        )

    except Exception as e:
        error_msg = f'Ocurrió un error al generar la nota de comodato para el ID {idComodato}: {e}'
        logger.error(error_msg, exc_info=True) 
        enviar_correo_error(
            asunto="Error en Sistema de Comodatos: Generación de PDF Agrupado",
            cuerpo=f"Ha ocurrido un error inesperado al intentar generar la nota de comodato en PDF para el ID: {idComodato}.\n\nDetalles del error: {error_msg}\n\nPor favor, revise los logs del servidor para más información."
        )
        flash(f'No se pudo generar la nota de comodato. Error: {e}', 'error')
        return redirect(url_for('comodatos.listar_comodatos'))
