# C:\Jubileo\models\condiciones_comodato.py

from extensions import db

class CondicionesComodato(db.Model):
    __tablename__ = 'condiciones_comodato'

    idComodato = db.Column(db.Integer, primary_key=True, autoincrement=True)
    NoFolio = db.Column(db.Integer, db.ForeignKey('cliente.NoFolio', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    motivoPrestamo = db.Column(db.String(255), nullable=False)
    otroMotivo = db.Column(db.String(255))
    fechaDevolucion = db.Column(db.Date, nullable=False)
    folioSustitucion = db.Column(db.String(255))
    cantidad = db.Column(db.Integer, nullable=False)
    UM = db.Column(db.String(50)) # Unidad de Medida
    concepto = db.Column(db.String(255), nullable=False)
    costo = db.Column(db.Numeric(10, 2))
    importe = db.Column(db.Numeric(10, 2))
    importeTotal = db.Column(db.Numeric(10, 2), nullable=False)
    notificado_vencimiento = db.Column(db.Boolean, default=False) # 0=False, 1=True
    

    # Relación con el cliente
    cliente = db.relationship('Cliente', backref='comodatos', lazy=True)

    def __repr__(self):
        return f"<CondicionesComodato {self.idComodato} - Cliente {self.NoFolio}>"

