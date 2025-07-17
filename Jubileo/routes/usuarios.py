# C:\Jubileo\routes\usuarios.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user # Importamos de Flask-Login
from extensions import db # Importamos db, asumiendo que está en extensions.py
from models import Usuario # Importamos el modelo Usuario
from utils.error_handler import enviar_correo_error # Importa la función de manejo de errores
import logging

logger = logging.getLogger(__name__)

# Define el Blueprint para los usuarios
# ¡IMPORTANTE! El nombre del Blueprint es 'usuarios_bp'
usuarios_bp = Blueprint('usuarios_bp', __name__, url_prefix='/usuarios')

# --- Ruta: Listar Usuarios ---
@usuarios_bp.route('/')
@login_required # Protege esta ruta con Flask-Login
def listar_usuarios():
    """
    Lista todos los usuarios. Requiere que el usuario esté logueado y sea administrador.
    """
    if not current_user.is_authenticated or not current_user.is_admin:
        flash('Acceso denegado. Solo administradores pueden ver esta sección.', 'danger')
        logger.warning(f"Intento de acceso no autorizado a /usuarios por usuario: {current_user.username if current_user.is_authenticated else 'Anónimo'}")
        return redirect(url_for('main_bp.index')) # Redirige al dashboard si no es admin

    error = None
    usuarios = []
    try:
        usuarios = Usuario.query.all() # Obtener todos los usuarios usando SQLAlchemy
        logger.info(f"Listando {len(usuarios)} usuarios.")
    except Exception as e:
        error = f'Ocurrió un error al listar los usuarios: {e}'
        logger.error(error, exc_info=True)
        enviar_correo_error(
            asunto="Error al listar usuarios",
            cuerpo=f"Ocurrió un error al intentar cargar la lista de usuarios.\n\nDetalles del error: {e}"
        )
        flash(error, 'error')
        return redirect(url_for('main_bp.index')) # Redirige al dashboard en caso de error
    return render_template('usuarios/listar.html', usuarios=usuarios, error=error)

# --- Ruta: Agregar Nuevo Usuario ---
@usuarios_bp.route('/agregar', methods=['GET', 'POST'])
@login_required # Protege esta ruta con Flask-Login
def agregar_usuario():
    """
    Agrega un nuevo usuario. Requiere que el usuario esté logueado y sea administrador.
    """
    if not current_user.is_authenticated or not current_user.is_admin:
        flash('Acceso denegado. Solo administradores pueden agregar usuarios.', 'danger')
        logger.warning(f"Intento de acceso no autorizado a /usuarios/agregar por usuario: {current_user.username if current_user.is_authenticated else 'Anónimo'}")
        return redirect(url_for('main_bp.index'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email') # Asumiendo que el campo 'email' existe en el formulario
        is_admin = 'is_admin' in request.form # Checkbox para admin status

        try:
            if not username or not password or not email:
                error = 'Nombre de usuario, email y contraseña son obligatorios.'
                flash(error, 'error')
                return render_template('usuarios/agregar.html', error=error, form=request.form)

            # Verificar si el nombre de usuario o email ya existen
            existing_user_by_username = Usuario.query.filter_by(username=username).first()
            existing_user_by_email = Usuario.query.filter_by(email=email).first()

            if existing_user_by_username:
                error = f'El nombre de usuario "{username}" ya existe.'
                flash(error, 'error')
                return render_template('usuarios/agregar.html', error=error, form=request.form)
            
            if existing_user_by_email:
                error = f'El email "{email}" ya está registrado.'
                flash(error, 'error')
                return render_template('usuarios/agregar.html', error=error, form=request.form)

            # Crear una nueva instancia del modelo Usuario y establecer la contraseña
            new_user = Usuario(username=username, email=email, is_admin=is_admin)
            new_user.set_password(password) # Usa el método del modelo para hashear

            db.session.add(new_user)
            db.session.commit()
            flash('Usuario agregado exitosamente.', 'success')
            logger.info(f"Nuevo usuario '{username}' agregado por {current_user.username}.")
            return redirect(url_for('usuarios_bp.listar_usuarios'))
        except Exception as e:
            error = f'Ocurrió un error al agregar el usuario: {e}'
            logger.error(error, exc_info=True)
            db.session.rollback()
            enviar_correo_error(
                asunto="Error al agregar usuario",
                cuerpo=f"Ocurrió un error al intentar agregar un nuevo usuario.\n\nDetalles del error: {e}\n\nDatos del formulario: {request.form}"
            )
            flash(error, 'error')
            return render_template('usuarios/agregar.html', error=error, form=request.form)
    return render_template('usuarios/agregar.html', error=error)

# --- Ruta: Editar Usuario ---
@usuarios_bp.route('/editar/<int:idUsuario>', methods=['GET', 'POST'])
@login_required # Protege esta ruta con Flask-Login
def editar_usuario(idUsuario):
    """
    Edita un usuario existente. Requiere que el usuario esté logueado y sea administrador.
    """
    if not current_user.is_authenticated or not current_user.is_admin:
        flash('Acceso denegado. Solo administradores pueden editar usuarios.', 'danger')
        logger.warning(f"Intento de acceso no autorizado a /usuarios/editar por usuario: {current_user.username if current_user.is_authenticated else 'Anónimo'}")
        return redirect(url_for('main_bp.index'))

    error = None
    try:
        usuario = Usuario.query.get(idUsuario) # Usamos .get() que es más eficiente para PK
        if not usuario:
            flash('Usuario no encontrado.', 'error')
            logger.warning(f"Intento de edición de usuario no existente: {idUsuario}.")
            return redirect(url_for('usuarios_bp.listar_usuarios'))

        if request.method == 'POST':
            new_username = request.form.get('username')
            new_email = request.form.get('email') # Asumiendo el campo email
            new_password = request.form.get('password') # Puede ser opcional
            is_admin = 'is_admin' in request.form

            if not new_username or not new_email:
                error = 'El nombre de usuario y el email son obligatorios.'
                flash(error, 'error')
                return render_template('usuarios/editar.html', error=error, usuario=usuario)

            # Verificar si el nuevo nombre de usuario ya existe y no es el del usuario actual
            existing_user_by_username = Usuario.query.filter_by(username=new_username).first()
            if existing_user_by_username and existing_user_by_username.id != idUsuario: # Usar .id para el PK
                error = f'El nombre de usuario "{new_username}" ya existe.'
                flash(error, 'error')
                return render_template('usuarios/editar.html', error=error, usuario=usuario)
            
            # Verificar si el nuevo email ya existe y no es el del usuario actual
            existing_user_by_email = Usuario.query.filter_by(email=new_email).first()
            if existing_user_by_email and existing_user_by_email.id != idUsuario:
                error = f'El email "{new_email}" ya está registrado.'
                flash(error, 'error')
                return render_template('usuarios/editar.html', error=error, usuario=usuario)

            usuario.username = new_username
            usuario.email = new_email
            usuario.is_admin = is_admin # Actualizar el estado de administrador
            if new_password: # Si se proporciona una nueva contraseña, hashearla
                usuario.set_password(new_password) # Usa el método del modelo
            
            db.session.commit()
            flash('Usuario actualizado exitosamente.', 'success')
            logger.info(f"Usuario '{usuario.username}' ({idUsuario}) actualizado por {current_user.username}.")
            return redirect(url_for('usuarios_bp.listar_usuarios'))
        
        return render_template('usuarios/editar.html', usuario=usuario, error=error)
    except Exception as e:
        error = f'Ocurrió un error al editar el usuario: {e}'
        logger.error(error, exc_info=True)
        db.session.rollback()
        enviar_correo_error(
            asunto="Error al editar usuario",
            cuerpo=f"Ocurrió un error al intentar editar el usuario con ID {idUsuario}.\n\nDetalles del error: {e}\n\nDatos del formulario: {request.form}"
        )
        flash(error, 'error')
        # Si hay un error grave que impide obtener el usuario, redirigimos a la lista
        return redirect(url_for('usuarios_bp.listar_usuarios'))

# --- Ruta: Eliminar Usuario ---
@usuarios_bp.route('/eliminar/<int:idUsuario>', methods=['POST'])
@login_required # Protege esta ruta con Flask-Login
def eliminar_usuario(idUsuario):
    """
    Elimina un usuario existente. Requiere que el usuario esté logueado y sea administrador.
    """
    if not current_user.is_authenticated or not current_user.is_admin:
        flash('Acceso denegado. Solo administradores pueden eliminar usuarios.', 'danger')
        logger.warning(f"Intento de acceso no autorizado a /usuarios/eliminar por usuario: {current_user.username if current_user.is_authenticated else 'Anónimo'}")
        return redirect(url_for('main_bp.index'))
    
    # Evitar que un administrador se elimine a sí mismo (opcional, pero buena práctica)
    if current_user.id == idUsuario:
        flash('No puedes eliminar tu propia cuenta de administrador.', 'warning')
        return redirect(url_for('usuarios_bp.listar_usuarios'))

    error = None
    try:
        usuario = Usuario.query.get(idUsuario)
        if not usuario:
            flash('Usuario no encontrado.', 'error')
            logger.warning(f"Intento de eliminación de usuario no existente: {idUsuario}.")
            return redirect(url_for('usuarios_bp.listar_usuarios'))
        
        db.session.delete(usuario)
        db.session.commit()
        flash('Usuario eliminado exitosamente.', 'success')
        logger.info(f"Usuario '{usuario.username}' ({idUsuario}) eliminado por {current_user.username}.")
        return redirect(url_for('usuarios_bp.listar_usuarios'))
    except Exception as e:
        error = f'Ocurrió un error al eliminar el usuario: {e}'
        logger.error(error, exc_info=True)
        db.session.rollback()
        enviar_correo_error(
            asunto="Error al eliminar usuario",
            cuerpo=f"Ocurrió un error al intentar eliminar el usuario con ID {idUsuario}.\n\nDetalles del error: {e}"
        )
        flash(error, 'error')
        return redirect(url_for('usuarios_bp.listar_usuarios'))

