
import logging
import os
import sys

# Asegúrate de que el directorio raíz de tu proyecto esté en el sys.path
# para que las importaciones como 'app' y 'models' funcionen correctamente.
# Asume que este script está en la raíz del proyecto y 'app.py' también.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'Jubileo')))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


from app import create_app # Importa create_app desde tu app.py
from app import verificar_vencimientos # Importa la función de verificación

# Configura el logger para este script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_scheduled_task():
    _app = create_app() # Crea una instancia de la aplicación
    with _app.app_context():
        logger.info("Iniciando ejecución manual de verificar_vencimientos desde Cron Job...")
        verificar_vencimientos()
        logger.info("Ejecución manual de verificar_vencimientos completada.")

if __name__ == '__main__':
    run_scheduled_task()
