import functools
from flask import Blueprint, render_template, session, request, redirect, url_for, flash, current_app
from werkzeug.security import check_password_hash
from extensions import db, mail 
from utils.error_handler import enviar_correo_error

# Importa Usuario desde models.usuario
from models.usuario import Usuario 

import logging

from flask_login import login_user, logout_user, LoginManager, current_user 

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def login_required(view):
    """View decorator that redirects anonymous users to the login page."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Logs in a registered user.

    Validates the username and password from the form and stores the user id
    in a session.
    """
    if request.method == 'POST':
        username = request.form.get('username') 
        password = request.form.get('password')
        error = None

        logger.debug(f"Intento de login para usuario: {username}")
        logger.debug(f"Contraseña ingresada (sin hash): {password}") 

        try:
            user = Usuario.query.filter_by(nombreUsuario=username).first()
            logger.debug(f"Usuario recuperado de la BD: {user}")

            if user is None:
                error = 'Nombre de usuario incorrecto.'
                logger.debug("Usuario no encontrado.")
            elif not user.check_password(password): 
                error = 'Contraseña incorrecta.'
                logger.debug("Contraseña no coincide.")
                logger.debug(f"Hash en BD: {user.contraseña}, Contraseña ingresada: {password}") 

            if error is None:
                login_user(user) 
                session['username'] = user.nombreUsuario 

                logger.debug(f"Sesión establecida para user_id: {user.idUsuario}, username: {session.get('username')}")
                flash('Inicio de sesión exitoso!', 'success') 

                # --- ¡CAMBIO AQUÍ! Elimina la lógica de next_page y redirige directamente ---
                logger.debug("Redirigiendo directamente a comodatos.listar_comodatos después del login...")
                return redirect(url_for('comodatos.listar_comodatos'))
                # --- FIN DEL CAMBIO ---

            else:
                flash(error, 'error')
                logger.debug(f"Error de validación: {error}. Renderizando login.html de nuevo.")
                return render_template('auth/login.html') 

        except Exception as e:
            error_message = f"Excepción inesperada durante el inicio de sesión: {e}"
            logger.error(error_message, exc_info=True) 
            flash(f"Ocurrió un error inesperado. Por favor, inténtalo de nuevo. Detalles: {e}", 'error')
            
            try:
                if enviar_correo_error and callable(enviar_correo_error):
                    enviar_correo_error(
                        asunto="Error de inicio de sesión",
                        cuerpo=f"Ocurrió un error al intentar iniciar sesión.\n\nDetalles del error: {e}\n\nDatos del formulario: {request.form}",
                    )
                else:
                    logger.error("enviar_correo_error no es una función o no está disponible.")
            except Exception as mail_e:
                logger.error(f"Error al intentar enviar el correo de error: {mail_e}", exc_info=True)

            return render_template('auth/login.html') 

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    """Logs out the user and clears the session."""
    logout_user() 
    session.clear() 
    flash('Has cerrado sesión exitosamente.', 'info') 
    return redirect(url_for('auth.login'))
