# C:\Jubileo\extensions.py

from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_apscheduler import APScheduler
from flask_login import LoginManager

# Inicializa la instancia de SQLAlchemy.
# No se le pasa la aplicación aquí, se inicializará después con db.init_app(app).
db = SQLAlchemy()

# Inicializa la instancia de Flask-Mail.
# No se le pasa la aplicación aquí, se inicializará después con mail.init_app(app).
mail = Mail()

# Inicializa la instancia de Flask-APScheduler.
# No se le pasa la aplicación aquí, se inicializará después con scheduler.init_app(app).
scheduler = APScheduler()

# Inicializa la instancia de Flask-Login.
# No se le pasa la aplicación aquí, se inicializará después con login_manager.init_app(app).
login_manager = LoginManager()

