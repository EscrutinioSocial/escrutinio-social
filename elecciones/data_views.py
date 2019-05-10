"""
Vistas con datos crudos
ej: http://localhost:8000/elecciones/resultados-parciales-gobernador-cordoba-2019.csv

"""
from elecciones.models import Eleccion, VotoMesaReportado
import django_excel as excel
from django.views.decorators.cache import cache_page


@cache_page(60 * 60)  # 1 hora
def resultado_parcial_eleccion(request, slug_eleccion, filetype):
    '''
    lista de paradas de transporte urbano de pasajeros
    '''
    eleccion = Eleccion.objects.get(slug=slug_eleccion)
    mesas_reportadas = VotoMesaReportado.objects.filter(eleccion=eleccion).order_by('mesa__numero')
    
    headers = ['seccion', 'circuito', 'centro de votacion', 'mesa']
    for opcion in eleccion.opciones.all():
        headers.append(opcion.nombre)

    csv_list = [headers]

    resultados = {}
    for mesa_reportada in mesas_reportadas:
        mesa = mesa_reportada.mesa
        opcion = mesa_reportada.opcion
        if mesa not in resultados.keys():
            resultados[mesa] = {}
        if opcion.nombre not in resultados[mesa].keys():
            resultados[mesa][opcion.nombre] = 0
        
        resultados[mesa][opcion.nombre] += mesa_reportada.votos
    
    for mesa, opciones in resultados.items():
        fila = [mesa.lugar_votacion.circuito.seccion.nombre,
                mesa.lugar_votacion.circuito.nombre,
                mesa.lugar_votacion.nombre,
                mesa.numero]
        for opcion, votos in opciones.items():
            fila.append(votos)

        csv_list.append(fila)

    return excel.make_response(excel.pe.Sheet(csv_list), filetype)