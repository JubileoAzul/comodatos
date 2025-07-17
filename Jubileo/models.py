# models.py
# Este archivo define los modelos de tu base de datos usando SQLAlchemy.
# Cada clase representa una tabla en tu base de datos.

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

# Modelo para la tabla 'clientes'
class Cliente(db.Model):
    __tablename__ = 'clientes' # Nombre de la tabla en la base de datos
    NoFolio = db.Column(db.Integer, primary_key=True)
    nombreComercial = db.Column(db.String(255), nullable=False)
    tipoCliente = db.Column(db.String(50))
    fechaPrestamo = db.Column(db.Date)
    ruta = db.Column(db.String(255))
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(255)) # Columna para el correo electrónico del cliente
    calle = db.Column(db.String(255))
    numero = db.Column(db.String(10))
    colonia = db.Column(db.String(255))
    municipio = db.Column(db.String(255))
    estado = db.Column(db.String(255))
    cp = db.Column(db.String(10))

    # Relación con CondicionComodato: un cliente puede tener muchos comodatos
    comodatos = db.relationship('CondicionComodato', backref='cliente', lazy=True)

    def __repr__(self):
        return f'<Cliente {self.nombreComercial}>'

# Modelo para la tabla 'condiciones_comodato'
class CondicionComodato(db.Model):
    __tablename__ = 'condiciones_comodato' # Nombre de la tabla en la base de datos
    idComodato = db.Column(db.Integer, primary_key=True)
    # Clave foránea que referencia a la tabla 'clientes'
    NoFolio = db.Column(db.Integer, db.ForeignKey('clientes.NoFolio'), nullable=False)
    motivoPrestamo = db.Column(db.String(255))
    otroMotivo = db.Column(db.String(255))
    fechaDevolucion = db.Column(db.Date)
    folioSustitucion = db.Column(db.String(50))
    cantidad = db.Column(db.Integer)
    UM = db.Column(db.String(50)) # Unidad de Medida
    concepto = db.Column(db.String(255))
    costo = db.Column(db.Float)
    importe = db.Column(db.Float)
    importeTotal = db.Column(db.Float)
    notificado_vencimiento = db.Column(db.Integer, default=0) # Para el seguimiento de notificaciones

    def __repr__(self):
        return f'<Comodato {self.concepto} - Cliente {self.NoFolio}>'