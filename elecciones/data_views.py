"""
Vistas con datos crudos
ej: http://localhost:8000/elecciones/resultados-parciales-gobernador-cordoba-2019.csv

"""
from elecciones.models import Categoria, VotoMesaReportado
import django_excel as excel
from django.views.decorators.cache import cache_page


@cache_page(60 * 5)  # 5 minutos
def resultado_parcial_categoria(request, slug_categoria, filetype):
    '''
    lista de paradas de transporte urbano de pasajeros
    '''
    categoria = Categoria.objects.get(slug=slug_categoria)
    mesas_reportadas = VotoMesaReportado.objects.filter(categoria=categoria).order_by('mesa__numero', 'opcion__orden')

    headers = ['seccion', 'numero seccion', 'circuito', 'codigo circuito', 'centro de votacion', 'mesa']
    for opcion in categoria.opciones.all().order_by('orden'):
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
                mesa.lugar_votacion.circuito.seccion.numero,
                mesa.lugar_votacion.circuito.nombre,
                mesa.lugar_votacion.circuito.numero,
                mesa.lugar_votacion.nombre,
                mesa.numero]
        for opcion, votos in opciones.items():
            fila.append(votos)

        csv_list.append(fila)

    return excel.make_response(excel.pe.Sheet(csv_list), filetype)