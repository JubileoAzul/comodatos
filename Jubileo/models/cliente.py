# C:\Jubileo\models\cliente.py

from extensions import db
from datetime import datetime

class Cliente(db.Model):
    __tablename__ = 'cliente' # Asegúrate de que el nombre de la tabla sea correcto (singular)

    NoFolio = db.Column(db.Integer, primary_key=True) 
    NoCliente = db.Column(db.String(255)) # ¡IMPORTANTE! Asegúrate que sea db.String
    nombreComercial = db.Column(db.String(255), nullable=False)
    tipoCliente = db.Column(db.String(50))
    fechaPrestamo = db.Column(db.Date) # No es necesario default=datetime.utcnow si se ingresa manualmente
    ruta = db.Column(db.String(100))
    telefono = db.Column(db.String(50))
    email = db.Column(db.String(255))
    calle = db.Column(db.String(255))
    numero = db.Column(db.String(50)) 
    colonia = db.Column(db.String(255))
    municipio = db.Column(db.String(100))
    estado = db.Column(db.String(100))
    cp = db.Column(db.String(10))

    def __repr__(self):
        return f"<Cliente {self.NoFolio} - {self.nombreComercial}>"

