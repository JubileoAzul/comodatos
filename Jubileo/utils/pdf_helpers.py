# C:\Jubileo\utils\pdf_helpers.py

from collections import defaultdict
from flask import render_template, current_app
import logging
from weasyprint import HTML, CSS

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
        'costo': 0.0, 
        'importe': 0.0,
        'importeTotal': 0.0 
    })

    for item in items:
        key = (item.concepto, item.UM)
        
        logger.debug(f"DEBUG_AGGREGATION: Processing item: Concepto='{item.concepto}', Cantidad={item.cantidad}, UM='{item.UM}', Costo={item.costo}, Importe={item.importe}, ImporteTotal={item.importeTotal}")

        cantidad_val = int(item.cantidad) if item.cantidad is not None else 0
        
        costo_val = 0.0
        importe_val = 0.0
        importe_total_val = 0.0

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

        # Intenta convertir 'importeTotal' a float, limpiando caracteres no numéricos
        if item.importeTotal is not None:
            try:
                cleaned_importe_total_str = str(item.importeTotal).replace('$', '').replace(',', '')
                importe_total_val = float(cleaned_importe_total_str)
            except (ValueError, TypeError):
                logger.error(f"ERROR_AGGREGATION: Could not convert importeTotal '{item.importeTotal}' to float for Concepto='{item.concepto}'. Defaulting to 0.0.")
                importe_total_val = 0.0

        logger.debug(f"DEBUG_AGGREGATION: Converted values: Cantidad={cantidad_val}, Costo={costo_val}, Importe={importe_val}, ImporteTotal={importe_total_val}")


        agregados[key]['cantidad'] += cantidad_val
        agregados[key]['UM'] = item.UM if item.UM else 'N/A'
        agregados[key]['concepto'] = item.concepto if item.concepto else 'N/A'

        # Asignar el costo unitario del primer artículo encontrado para este grupo, si aún no está asignado
        if agregados[key]['costo'] == 0.0 and costo_val != 0.0: # Solo actualiza si el costo agregado es 0 y el costo_val es válido
             agregados[key]['costo'] = costo_val

        agregados[key]['importe'] += importe_val
        agregados[key]['importeTotal'] += importe_total_val
        
        logger.debug(f"DEBUG_AGGREGATION: After adding to aggregated[{key}]: Current Importe for key='{key}' is {agregados[key]['importe']:.2f}, Current ImporteTotal for key='{key}' is {agregados[key]['importeTotal']:.2f}")
    
    final_aggregated_list = list(agregados.values())
    logger.debug(f"DEBUG_AGGREGATION: Final aggregated list before return: {final_aggregated_list}")
    return final_aggregated_list


def _render_pdf_template_for_email(cliente_obj, comodato_items_list, main_comodato_ref_obj, total_importe_para_email):
    """
    Renders the comodato_note.html template specifically for email attachments.
    Requires an app context.
    """
    datos_empresa = {
        'nombre_empresa': 'Jubileo Azul S.A. de C.V.',
        'rfc_empresa': 'JAZ990101XYZ', 
        'direccion_empresa': 'AV. CRUZ AZUL S/N COL. CENTRO, CD. COOPERATIVA CRUZ AZUL, TULA DE ALLENDE, HGO. C.P. 42840', 
        'telefono_empresa': '(S) 01 (773) 785 1962 / 785 2231', 
        'email_empresa': 'plantajubileo@prodigy.net.mx', 
    }
    return render_template(
        'pdf_templates/comodato_note.html',
        cliente=cliente_obj, 
        comodato_items=comodato_items_list,
        datos_empresa=datos_empresa,
        main_comodato_ref=main_comodato_ref_obj,
        grand_total_importe=total_importe_para_email # Pasamos el total calculado desde Python
    )
