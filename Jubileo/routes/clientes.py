# C:\Jubileo\routes\clientes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user # Usamos el login_required de Flask-Login
from utils.error_handler import enviar_correo_error  # Importa la función de manejo de errores
from extensions import db  # Importa la instancia de SQLAlchemy, asumiendo que db está aquí
from models import Cliente # Importa el modelo Cliente
from datetime import datetime, date # Importar datetime Y date para manejo de fechas
import logging

logger = logging.getLogger(__name__)

# Define el Blueprint para los clientes
# ¡IMPORTANTE! El nombre del Blueprint es 'clientes_bp'
clientes_bp = Blueprint('clientes_bp', __name__, url_prefix='/clientes')

# --- Ruta: Listar Clientes ---
@clientes_bp.route('/')
@login_required # Protege esta ruta con Flask-Login
def listar_clientes():
    """
    Lista todos los clientes.
    """
    error = None
    clientes = []
    try:
        # Usar el modelo Cliente de SQLAlchemy para obtener todos los clientes
        clientes = Cliente.query.all()
        logger.info(f"Listando {len(clientes)} clientes.")
    except Exception as e:
        error = f'Ocurrió un error al listar los clientes: {e}'
        logger.error(error, exc_info=True)
        enviar_correo_error(
            asunto="Error al listar clientes",
            cuerpo=f"Ocurrió un error al intentar cargar la lista de clientes.\n\nDetalles del error: {e}"
        )
        flash(error, 'error')
        # Si hay un error al listar, redirige al dashboard principal
        return redirect(url_for('main_bp.index')) 
    return render_template('clientes/listar.html', clientes=clientes, error=error)

# --- Ruta: Agregar Nuevo Cliente ---
@clientes_bp.route('/agregar', methods=['GET', 'POST'])
@login_required # Protege esta ruta con Flask-Login
def agregar_cliente():
    """
    Agrega un nuevo cliente.
    """
    error = None
    if request.method == 'POST':
        NoFolio = request.form.get('NoFolio')
        fechaPrestamo_str = request.form.get('fechaPrestamo')
        tipoCliente = request.form.get('tipoCliente')
        ruta = request.form.get('ruta')
        nombreComercial = request.form.get('nombreComercial')
        telefono = request.form.get('telefono')
        calle = request.form.get('calle')
        numero = request.form.get('numero')
        colonia = request.form.get('colonia')
        municipio = request.form.get('municipio')
        estado = request.form.get('estado')
        cp = request.form.get('cp')
        email = request.form.get('email')

        try:
            # Convertir fechaPrestamo de string a objeto date
            fechaPrestamo_obj = datetime.strptime(fechaPrestamo_str, '%Y-%m-%d').date() if fechaPrestamo_str else None

            # Validaciones
            if not NoFolio or not nombreComercial:
                error = 'NoFolio y Nombre Comercial son campos obligatorios.'
                flash(error, 'error')
                return render_template('clientes/agregar.html', error=error, form=request.form)

            # Verificar si el NoFolio ya existe usando SQLAlchemy
            existing_client = Cliente.query.filter_by(NoFolio=NoFolio).first()
            if existing_client:
                error = f'Ya existe un cliente con el NoFolio: {NoFolio}'
                flash(error, 'error')
                return render_template('clientes/agregar.html', error=error, form=request.form)

            # Crear una nueva instancia del modelo Cliente
            new_client = Cliente(
                NoFolio=NoFolio,
                fechaPrestamo=fechaPrestamo_obj, # Usar el objeto date
                tipoCliente=tipoCliente,
                ruta=ruta,
                nombreComercial=nombreComercial,
                telefono=telefono,
                calle=calle,
                numero=numero,
                colonia=colonia,
                municipio=municipio,
                estado=estado,
                cp=cp,
                email=email
            )
            
            # Añadir y guardar en la base de datos
            db.session.add(new_client)
            db.session.commit()
            flash('Cliente agregado exitosamente.', 'success')
            return redirect(url_for('clientes_bp.listar_clientes')) # Redirige a la lista de clientes
        except Exception as e:
            error = f'Ocurrió un error al agregar el cliente: {e}'
            logger.error(error, exc_info=True)
            db.session.rollback() # Hacer rollback en caso de error
            enviar_correo_error(
                asunto="Error al agregar cliente",
                cuerpo=f"Ocurrió un error al intentar agregar un nuevo cliente.\n\nDetalles del error: {e}\n\nDatos del formulario: {request.form}"
            )
            flash(error, 'error')
            return render_template('clientes/agregar.html', error=error, form=request.form)
    return render_template('clientes/agregar.html', error=error)

# --- Ruta: Editar Cliente ---
@clientes_bp.route('/editar/<string:NoFolio>', methods=['GET', 'POST'])
@login_required # Protege esta ruta con Flask-Login
def editar_cliente(NoFolio):
    """
    Edita un cliente existente.
    """
    error = None
    cliente = None # Declarar cliente al inicio para asegurar su disponibilidad

    try:
        # Obtener el cliente a editar usando SQLAlchemy
        cliente = Cliente.query.filter_by(NoFolio=NoFolio).first()

        if not cliente:
            error = f'No se encontró ningún cliente con el NoFolio: {NoFolio}'
            flash(error, 'error')
            return redirect(url_for('clientes_bp.listar_clientes')) # Redirige a la lista si no se encuentra

        if request.method == 'POST':
            # Recolectar fechaPrestamo como string
            fechaPrestamo_str = request.form.get('fechaPrestamo')

            # Actualizar los atributos del objeto cliente
            cliente.tipoCliente = request.form.get('tipoCliente')
            cliente.ruta = request.form.get('ruta')
            cliente.nombreComercial = request.form.get('nombreComercial')
            cliente.telefono = request.form.get('telefono')
            cliente.calle = request.form.get('calle')
            cliente.numero = request.form.get('numero')
            cliente.colonia = request.form.get('colonia')
            cliente.municipio = request.form.get('municipio')
            cliente.estado = request.form.get('estado')
            cliente.cp = request.form.get('cp')
            cliente.email = request.form.get('email')

            # Convertir fechaPrestamo a tipo Date si es necesario
            cliente.fechaPrestamo = datetime.strptime(fechaPrestamo_str, '%Y-%m-%d').date() \
                                     if fechaPrestamo_str else None

            # Validaciones (mantener las del formulario POST)
            if not cliente.nombreComercial:
                error = 'Nombre Comercial es un campo obligatorio.'
                flash(error, 'error')
                return render_template('clientes/editar.html', error=error, cliente=cliente)

            db.session.commit() # Guardar los cambios
            flash('Cliente actualizado exitosamente.', 'success')
            return redirect(url_for('clientes_bp.listar_clientes')) # Redirige a la lista
    except Exception as e:
        error = f'Ocurrió un error al editar el cliente: {e}'
        logger.error(error, exc_info=True)
        db.session.rollback()
        enviar_correo_error(
            asunto="Error al editar cliente",
            cuerpo=f"Ocurrió un error al intentar editar el cliente con NoFolio {NoFolio}.\n\nDetalles del error: {e}\n\nDatos del formulario: {request.form}"
        )
        flash(error, 'error')
        # Redirige en caso de error grave. Si cliente no se pudo cargar, no podemos renderizarlo.
        return redirect(url_for('clientes_bp.listar_clientes'))

    # Para GET request, pasar el objeto cliente al template
    return render_template('clientes/editar.html', cliente=cliente, error=error)

# --- Ruta: Eliminar Cliente ---
@clientes_bp.route('/eliminar/<string:NoFolio>', methods=['POST'])
@login_required # Protege esta ruta con Flask-Login
def eliminar_cliente(NoFolio):
    """
    Elimina un cliente existente.
    """
    error = None
    try:
        # Obtener el cliente a eliminar
        cliente = Cliente.query.filter_by(NoFolio=NoFolio).first()
        if not cliente:
            error = f'No se encontró ningún cliente con el NoFolio: {NoFolio}'
            flash(error, 'error')
            return redirect(url_for('clientes_bp.listar_clientes')) # Redirige si no se encuentra

        db.session.delete(cliente) # Eliminar el cliente
        db.session.commit()
        flash('Cliente eliminado exitosamente.', 'success')
        return redirect(url_for('clientes_bp.listar_clientes')) # Redirige a la lista
    except Exception as e:
        error = f'Ocurrió un error al eliminar el cliente: {e}'
        logger.error(error, exc_info=True)
        db.session.rollback()
        enviar_correo_error(
            asunto="Error al eliminar cliente",
            cuerpo=f"Ocurrió un error al intentar eliminar el cliente con NoFolio {NoFolio}.\n\nDetalles del error: {e}"
        )
        flash(error, 'error')
        return redirect(url_for('clientes_bp.listar_clientes')) # Redirige si hay error

# --- Ruta: Ver Detalles de Cliente ---
@clientes_bp.route('/ver/<string:NoFolio>')
@login_required # Protege esta ruta con Flask-Login
def ver_cliente(NoFolio):
    """
    Muestra los detalles de un cliente.
    """
    error = None
    try:
        # Obtener el cliente
        cliente = Cliente.query.filter_by(NoFolio=NoFolio).first()

        if not cliente:
            error = f'No se encontró ningún cliente con el NoFolio: {NoFolio}'
            flash(error, 'error')
            return redirect(url_for('clientes_bp.listar_clientes')) # Redirige si no se encuentra

        return render_template('clientes/ver.html', cliente=cliente, error=error)
    except Exception as e:
        error = f'Ocurrió un error al ver el cliente: {e}'
        logger.error(error, exc_info=True)
        enviar_correo_error(
            asunto="Error al ver cliente",
            cuerpo=f"Ocurrió un error al intentar ver el cliente con NoFolio {NoFolio}.\n\nDetalles del error: {e}"
        )
        flash(error, 'error')
        return redirect(url_for('clientes_bp.listar_clientes')) # Redirige si hay error

