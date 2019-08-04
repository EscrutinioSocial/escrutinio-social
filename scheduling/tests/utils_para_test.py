def verificar_registro_prioridad(regi, desde_proporcion, hasta_proporcion, prioridad, hasta_cantidad=None):
    assert regi.desde_proporcion == desde_proporcion
    assert regi.hasta_proporcion == hasta_proporcion
    assert regi.prioridad == prioridad
    assert regi.hasta_cantidad == hasta_cantidad

def asignar_prioridades_standard(settings):
    settings.PRIORIDADES_STANDARD_SECCION = [
        {'desde_proporcion': 0, 'hasta_proporcion': 2, 'prioridad': 2},
        {'desde_proporcion': 2, 'hasta_proporcion': 10, 'prioridad': 20},
        {'desde_proporcion': 10, 'hasta_proporcion': 100, 'prioridad': 100},
    ]
    settings.PRIORIDADES_STANDARD_CATEGORIA = [
        {'desde_proporcion': 0, 'hasta_proporcion': 100, 'prioridad': 100},
    ]
