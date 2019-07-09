from rest_framework.decorators import api_view, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FileUploadParser, JSONParser
from rest_framework import authentication, permissions, status

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import (
    VotoSerializer, ActaSerializer, MesaSerializer
)


@swagger_auto_schema(
    method='post',
    request_body=ActaSerializer, 
    tags=['Actas'],
    responses={
        status.HTTP_201_CREATED : openapi.Response(
            description='La imagen fue subida con éxito',
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'foto_digest': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description='Hash digest único de 128 digitos hexadecimales'
                    )
                }
            ),
            examples={'Caso exitoso': {'foto_digest': '90554e1d519e0fc665fab042d7499a1bc9c191f2a13b0b2c369753dcb23b181866cb116007fc37a445421270e04912a46dbfb6a325cf27a2603eed45fc1d41b1'}}
        )
    },

)
@api_view(['POST'],)
@parser_classes((MultiPartParser, ))
def subir_acta(request):
    """
    Permite subir la foto de un acta sin identificar.

    En caso de éxito se devuelve el hash de la foto que puede 
    ser usado posteriomente para identificar el acta y cargar votos.
    """
    return Response({'foto_digest': ''}, status=201)


@swagger_auto_schema(
    method='put', 
    request_body=MesaSerializer,
    responses={
        status.HTTP_200_OK: openapi.Response(
            description='El acta fue identificada con éxito.',
        ),
        status.HTTP_404_NOT_FOUND: openapi.Response(
            description='No se encontro la mesa de votación.',
        ),
    },
    tags=['Actas']
)
@api_view(['PUT'],)
def identificar_acta(request, foto_digest):
    """
    Permite identificar la foto de un acta.

    Establece la relación entre la foto del acta y una mesa de votación especifica.
    """
    return Response({'mensaje': 'El acta fue identificada con éxito.'})
    

@swagger_auto_schema(
    method='post', 
    request_body=VotoSerializer,
    responses={
        status.HTTP_201_CREATED: openapi.Response(
            description='Se cargaron los votos para la opción y categoria dadas con éxito.',
        ),
        status.HTTP_404_NOT_FOUND: openapi.Response(
            description='No se encontraron la opción y/o la categoria.',
        ),
        status.HTTP_409_CONFLICT: openapi.Response(
            description='El acta todavia no fue identificada.',
        )
    },
    tags=['Actas']
)
@api_view(['POST'],)
def cargar_votos(request, foto_digest):
    """
    Permite cargar votos para un acta previamente identificada.

    Si ya existiera una carga de votos para la misma mesa, opcion y categoria,
    se actualizará el numero de votos con la version más reciente.
    """
    return Response({"mensaje": "Se cargaron los votos con éxito."}, status=201)
    