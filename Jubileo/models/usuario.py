from extensions import db
from datetime import datetime
from flask_login import UserMixin # Necesario para Flask-Login
from werkzeug.security import generate_password_hash, check_password_hash # Para hashear y verificar contraseñas

print(f"DEBUG: Cargando models.py desde: {__file__}") # <--- ¡AÑADE ESTA LÍNEA!

class Usuario(UserMixin, db.Model): # ¡IMPORTANTE! Heredar de UserMixin
    __tablename__ = 'usuarios' # Nombre de la tabla en la base de datos
    idUsuario = db.Column(db.Integer, primary_key=True) # ID del usuario
    nombreUsuario = db.Column(db.String(255), unique=True, nullable=False) # Nombre de usuario único
    contraseña = db.Column(db.String(255), nullable=False) # Almacena la contraseña hasheada
        # Defino explícitamente is_active para que siempre devuelva True
    # Esto esencialmente "desactiva" la verificación de actividad si no necesitas
    # controlar el estado activo/inactivo de un usuario.
    @property
    def is_active(self):
        """Siempre devuelve True, ya que no estamos gestionando usuarios inactivos."""
        return True

    # Métodos para Flask-Login (requeridos por UserMixin)
    def get_id(self):
        # Flask-Login necesita este método para obtener el ID del usuario
        return str(self.idUsuario)

    # Métodos para establecer y verificar la contraseña
    def set_password(self, password):
        """Hashea la contraseña y la guarda en el campo 'contraseña'."""
        self.contraseña = generate_password_hash(password)

    def check_password(self, password):
        """Verifica si la contraseña proporcionada coincide con la contraseña hasheada."""
        return check_password_hash(self.contraseña, password)

    def __repr__(self):
        # Representación de cadena del objeto Usuario, útil para depuración
        return f'<Usuario {self.nombreUsuario}>'
