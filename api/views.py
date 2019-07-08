from rest_framework.decorators import api_view, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FileUploadParser
from rest_framework import authentication, permissions, status

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import CargaSerializer, CargasCSVSerializer


@swagger_auto_schema(
    method='post', 
    request_body=CargaSerializer, tags=['Cargas']
)
@parser_classes((MultiPartParser,))
@api_view(['POST'],)
def crear_carga(request, mesa, categoria):
    """
    Permite la creación y/o actualización de actas individuales con una imagen adjunta.

    La mesa y la categoria se extraen de la url. La imagen adjunta es requerida.
    Opcionalmente se pueden enviar el fiscal y una lista con los votos por opción.

    Las cargas nuevas serán creadas con el atributo `origen='json'`.

    Una misma acta podrá recibirse varias veces (por cargas parciales y/o correcciones de errores). 
    
    Si una acta para la misma mesa y categoria ya existe en la BD, se asigna la imagen
    a dicha acta. Además, cuando la lista con votos por opción este presente, se 
    reemplaza completamente la lista anterior que pudiese existir o no.
    """
    return Response({"mensaje": "Carga creada con éxito."}, status=201)
    

@swagger_auto_schema(
    method='post', 
    request_body=CargasCSVSerializer, 
    responses={
        status.HTTP_200_OK : openapi.Response(
            description="Resultado de la importación",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'message': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description='Una breve descripción del resultado'
                    )
                }
            ),
            examples={'Caso exitoso': {'message': 'Se importaron 500 actas con éxito.'}}
        )
    },
    tags=['Cargas'])
@parser_classes((FileUploadParser,))
@api_view(['POST'],)
def importar_cargas(request):
    """
    Permite la importación de actas desde un archivo CSV.

    Se espera un archivo CSV con columnas:
    - mesa
    - categoria
    - n_opciones
    - opcion_1
    - votos_1
    - ...
    - opcion_n
    - votos_n

    Las cargas serán creadas con el atributo `origen='csv'`.
    
    Las imágenes correspondientes a cada acta pueden cargarse en requests separadas
    al end-point para crear y/o actualizar actas individuales.
    """
    return Response({"mensaje": "Se importaron N actas con éxito."})
