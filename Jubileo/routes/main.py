
import logging
from flask import Blueprint, render_template, redirect, request, url_for, flash
from flask_login import login_required, current_user, login_user, logout_user # Necesitas esto si el login/logout también va aquí

# Define el Blueprint para las rutas principales
main_bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)



@main_bp.route('/')
@login_required # Protege la ruta principal para que solo usuarios logueados puedan acceder
def index():
    """
    Ruta de la página principal (dashboard) de la aplicación.
    Requiere que el usuario esté autenticado para acceder.
    """
    logger.info(f"Usuario {current_user.nombreUsuario} accedió a la página principal.")
    return render_template('comodatos/listar.html')

# Puedes añadir otras rutas relacionadas con la funcionalidad "principal" aquí
# Por ejemplo, si el login/logout no está en su propio blueprint 'auth', podría ir aquí.

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Ruta para el inicio de sesión de usuarios.
    """
    # Si ya está logueado, redirige a la página principal
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    # Lógica para manejar el formulario de login (esto es un esqueleto)
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # Aquí iría tu lógica para verificar las credenciales con la base de datos
        # Ejemplo: user = User.query.filter_by(username=username).first()
        # if user and user.check_password(password):
        #     login_user(user)
        #     flash('Inicio de sesión exitoso.', 'success')
        #     return redirect(url_for('main.index'))
        # else:
        #     flash('Credenciales inválidas.', 'danger')
        flash('La lógica de inicio de sesión debe ser implementada.', 'info')
        return render_template('login.html', error="Credenciales inválidas (simulado)") # O un error real
    
    return render_template('login.html')

@main_bp.route('/logout')
@login_required
def logout():
    """
    Ruta para cerrar la sesión del usuario.
    """
    logout_user()
    flash('Has cerrado sesión exitosamente.', 'success')
    return redirect(url_for('main.login')) # Redirige a la página de login después de cerrar sesión
