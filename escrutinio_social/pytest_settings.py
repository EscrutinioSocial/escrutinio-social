from escrutinio_social.settings import *

MIN_COINCIDENCIAS_IDENTIFICACION = 2
MIN_COINCIDENCIAS_CARGAS = 2
MIN_COINCIDENCIAS_IDENTIFICACION_PROBLEMA = 2
MIN_COINCIDENCIAS_CARGAS_PROBLEMA = 2


CONSTANCE_CONFIG.update({
    'SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL': (1500, 'Valor de scoring que debe superar un fiscal para que la aplicación lo considere troll.', int),
    'SCORING_TROLL_IDENTIFICACION_DISTINTA_A_CONFIRMADA': (200, 'Cuánto aumenta el scoring de troll por una identificacion distinta a la confirmada.', int),
    'SCORING_TROLL_PROBLEMA_MESA_CATEGORIA_CON_CARGA_CONFIRMADA': (200, 'Cuánto aumenta el scoring de troll por poner "problema" en una MesaCategoria para la que se confirmaron cargas.', int),
    'SCORING_TROLL_PROBLEMA_DESCARTADO': (200, 'Cuánto aumenta el scoring de troll al descartarse un "problema" que él reporto.', int),
    'SCORING_TROLL_DESCUENTO_ACCION_CORRECTA': (50, 'Cuánto disminuye el scoring de troll para cada acción aceptada de un fiscal.', int),
    'UMBRAL_EXCLUIR_TAREAS_FISCAL': (300, 'Si hay menos de este número de usuaries actives, no le presentamos a le fiscal tareas en las que haya estado involucrade.', int),
})
