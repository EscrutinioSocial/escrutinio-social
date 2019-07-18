from django.shortcuts import get_object_or_404

from rest_framework.decorators import api_view, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FileUploadParser, JSONParser
from rest_framework import authentication, permissions, status

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import (
    VotoSerializer, ActaSerializer, MesaSerializer, CategoriaSerializer, OpcionSerializer,
    ListarCategoriasQuerySerializer, ListarOpcionesQuerySerializer
)

from adjuntos.models import Identificacion, Attachment
from elecciones.models import Distrito, Seccion, Circuito, Mesa


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
    serializer = ActaSerializer(data=request.data)
    if serializer.is_valid():
        attachment = serializer.save()
        return Response(data=ActaSerializer(attachment).data, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='put', 
    request_body=MesaSerializer,
    responses={
        status.HTTP_200_OK: openapi.Response(
            description='El acta fue identificada con éxito.',
        ),
        status.HTTP_404_NOT_FOUND: openapi.Response(
            description='No se existe la mesa de votación.',
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
    attachment = get_object_or_404(Attachment, foto_digest=foto_digest)
    serializer = MesaSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data

        distrito = get_object_or_404(Distrito, numero=data['codigo_distrito'])
        seccion = get_object_or_404(Seccion, distrito=distrito, numero=data['codigo_seccion'])
        circuito = get_object_or_404(Circuito, seccion=seccion, numero=data['codigo_circuito'])
        mesa = get_object_or_404(Mesa, circuito=circuito, numero=data['codigo_mesa'])
        
        identificacion = Identificacion(
            # No deberia ser 'api' ??
            source='telegram',
            status = Identificacion.STATUS.identificada,
            attachment=attachment,
            fiscal=request.user.fiscal,
            mesa=mesa
        )
        identificacion.save()

        return Response({'mensaje': 'El acta fue identificada con éxito.'})
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

@swagger_auto_schema(
    method='post', 
    request_body=VotoSerializer(many=True),
    responses={
        status.HTTP_201_CREATED: openapi.Response(
            description='Se cargaron los votos con éxito.',
        ),
        status.HTTP_404_NOT_FOUND: openapi.Response(
            description='No se encontraron alguna opción y/o categoría.',
        ),
        status.HTTP_409_CONFLICT: openapi.Response(
            description='El acta todavía no fue identificada.',
        ),
    },
    tags=['Actas']
)
@api_view(['POST'],)
def cargar_votos(request, foto_digest):
    """
    Permite cargar votos para un acta previamente identificada.

    La lista de votos debe contener al mebnos todas las opciones prioritarias.
    """
    return Response({"mensaje": "Se cargaron los votos con éxito."}, status=201)
    

@swagger_auto_schema(
    method='get', 
    query_serializer=ListarCategoriasQuerySerializer,
    responses={
        status.HTTP_200_OK: CategoriaSerializer(many=True)
    },
    tags=['Categorias']
)
@api_view(['GET'],)
def listar_categorias(request):
    """
    Permite listar las categorías de la elección

    Se listan todas las categorías con prioridad menor o igual un valor dado.
    Por defecto se listan sólo categorias principales y secundarias (`prioridad=2`).
    Las categorias se ordenan primero por prioridad ascendente y luego alfabeticamente.
    """
    return Response([])
    

@swagger_auto_schema(
    method='get', 
    query_serializer=ListarOpcionesQuerySerializer,
    responses={
        status.HTTP_200_OK: OpcionSerializer(many=True)
    },
    tags=['Opciones']
)
@api_view(['GET'],)
def listar_opciones(request, id_categoria):
    """
    Permite listar las opciones por categorías.

    Por defecto se listan sólo las opciones prioritarias (`solo_prioritarias=true`).
    Las opciones se ordenan de forma ascendente según el campo orden (orden en la boleta).
    """
    return Response([])
