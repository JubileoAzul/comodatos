# C:\Jubileo\utils\pdf_helpers.py

from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

def _agregar_articulos_comodato(items):
    """
    Agrupa y suma los artículos de comodato que tienen el mismo concepto y unidad de medida.
    Retorna una lista de diccionarios con los artículos agregados, asegurando que los valores numéricos
    sean tratados como floats para la suma. Maneja la limpieza de caracteres no numéricos.
    """
    agregados = defaultdict(lambda: {
        'cantidad': 0,
        'UM': '',
        'concepto': '',
        'costo': 0.0, # Costo unitario, se toma del primer item válido
        'importe': 0.0, # Suma de los importes de los items individuales agrupados
    })

    for item in items:
        key = (item.concepto, item.UM)
        
        logger.debug(f"DEBUG_AGGREGATION: Processing item: Concepto='{item.concepto}', Cantidad={item.cantidad}, UM='{item.UM}', Costo={item.costo}, Importe={item.importe}")

        cantidad_val = int(item.cantidad) if item.cantidad is not None else 0
        
        costo_val = 0.0
        importe_val = 0.0

        # Intenta convertir 'costo' a float, limpiando caracteres no numéricos
        if item.costo is not None:
            try:
                # Elimina caracteres comunes no numéricos como '$' y ',' antes de la conversión
                cleaned_costo_str = str(item.costo).replace('$', '').replace(',', '')
                costo_val = float(cleaned_costo_str)
            except (ValueError, TypeError):
                logger.error(f"ERROR_AGGREGATION: Could not convert costo '{item.costo}' to float for Concepto='{item.concepto}'. Defaulting to 0.0.")
                costo_val = 0.0
        
        # Intenta convertir 'importe' a float, limpiando caracteres no numéricos
        if item.importe is not None:
            try:
                cleaned_importe_str = str(item.importe).replace('$', '').replace(',', '')
                importe_val = float(cleaned_importe_str)
            except (ValueError, TypeError):
                logger.error(f"ERROR_AGGREGATION: Could not convert importe '{item.importe}' to float for Concepto='{item.concepto}'. Defaulting to 0.0.")
                importe_val = 0.0

        logger.debug(f"DEBUG_AGGREGATION: Converted values: Cantidad={cantidad_val}, Costo={costo_val}, Importe={importe_val}")

        agregados[key]['cantidad'] += cantidad_val
        agregados[key]['UM'] = item.UM if item.UM else 'N/A'
        agregados[key]['concepto'] = item.concepto if item.concepto else 'N/A'

        # Asignar el costo unitario del primer artículo encontrado para este grupo que tenga un costo válido
        # Esto evita sobrescribir un costo válido con 0.0 si un item posterior tiene costo nulo/inválido.
        if costo_val != 0.0 and (agregados[key]['costo'] == 0.0 or agregados[key]['costo'] == None):
             agregados[key]['costo'] = costo_val
        # Si el costo ya está establecido y el nuevo costo_val es diferente y válido, podrías querer loguear una advertencia
        # o decidir qué costo prevalece. Por ahora, mantenemos el primero válido.

        agregados[key]['importe'] += importe_val
        
        logger.debug(f"DEBUG_AGGREGATION: After adding to aggregated[{key}]: Current Importe for key='{key}' is {agregados[key]['importe']:.2f}")
    
    final_aggregated_list = list(agregados.values())
    logger.debug(f"DEBUG_AGGREGATION: Final aggregated list before return: {final_aggregated_list}")
    return final_aggregated_list
