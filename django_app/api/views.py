from collections import defaultdict

from django.shortcuts import get_object_or_404

from django.db import transaction
from django.db.utils import IntegrityError

from rest_framework.decorators import api_view, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import status

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import (
    VotoSerializer, ActaSerializer, MesaSerializer, CategoriaSerializer, OpcionSerializer,
    ListarCategoriasQuerySerializer, ListarOpcionesQuerySerializer
)

from adjuntos.models import Identificacion, Attachment, hash_file
from elecciones.models import (
    Distrito, Seccion, Circuito, Mesa, MesaCategoria, CategoriaOpcion, Categoria, Carga, VotoMesaReportado
)


@swagger_auto_schema(
    method='post',
    request_body=ActaSerializer,
    tags=['Actas'],
    responses={
        status.HTTP_201_CREATED:
        openapi.Response(
            description='La imagen fue subida con éxito',
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'foto_digest':
                    openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description='Hash digest único de 128 digitos hexadecimales'
                    )
                }
            ),
            examples={
                'Caso exitoso': {
                    'foto_digest':
                    '90554e1d519e0fc665fab042d7499a1bc9c191f2a13b0b2c369753dcb23b181866cb116007fc37a445421270e04912a46dbfb6a325cf27a2603eed45fc1d41b1'  # noqa
                }
            }
        )
    },
)
@api_view(
    ['POST'],
)
@parser_classes((MultiPartParser, ))
def subir_acta(request):
    """
    Permite subir la foto de un acta sin identificar.

    En caso de éxito se devuelve el hash de la foto que puede
    ser usado posteriomente para identificar el acta.
    """
    serializer = ActaSerializer(data=request.data)
    if serializer.is_valid():

        try:
            with transaction.atomic():
                attachment = serializer.save(subido_por=request.user.fiscal)
        except IntegrityError:
            # la imagen ya existe.
            # se obtiene la instancia conocida con el mismo hash
            foto = serializer.validated_data['foto']
            foto.seek(0)
            attachment = Attachment.objects.filter(foto_digest=hash_file(foto)).first()

            return Response(data=ActaSerializer(attachment).data, status=status.HTTP_409_CONFLICT)

        return Response(data=ActaSerializer(attachment).data, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='put',
    request_body=MesaSerializer,
    responses={
        status.HTTP_200_OK:
        openapi.Response(
            description='El acta fue identificada con éxito.',
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'id':
                    openapi.Schema(
                        type=openapi.TYPE_INTEGER,
                        description='El ID de la mesa de votación con la que se identificó el acta'
                    )
                }
            ),
        ),
        status.HTTP_400_BAD_REQUEST:
        openapi.Response(description='Errores de validación.', ),
        status.HTTP_404_NOT_FOUND:
        openapi.Response(description='No existe la mesa de votación.', ),
    },
    tags=['Actas']
)
@api_view(
    ['PUT'],
)
def identificar_acta(request, foto_digest):
    """
    Permite identificar la foto de un acta.

    Establece la relación entre la foto del acta y una mesa de votación especifica.
    En caso de éxito se devuelve el `id_mesa` que puede ser usado posteriormente para
    cargar los votos.
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
            source=Identificacion.SOURCES.telegram,
            status=Identificacion.STATUS.identificada,
            attachment=attachment,
            fiscal=request.user.fiscal,
            mesa=mesa
        )
        identificacion.save()

        return Response({'id': mesa.id})
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    request_body=VotoSerializer(many=True, allow_empty=False),
    responses={
        status.HTTP_201_CREATED: openapi.Response(description='Se cargaron los votos con éxito.', ),
        status.HTTP_400_BAD_REQUEST: openapi.Response(description='Errores de validación.', ),
        status.HTTP_404_NOT_FOUND: openapi.Response(description='No existe la mesa de votación.', )
    },
    tags=['Actas']
)
@api_view(
    ['POST'],
)
def cargar_votos(request, id_mesa):
    """
    Permite cargar votos para una mesa de votación especifica.

    La lista de votos debe contener al menos todas las opciones prioritarias.
    """
    mesa = get_object_or_404(Mesa, id=id_mesa)
    serializer = VotoSerializer(data=request.data, many=True, allow_empty=False)
    if serializer.is_valid():
        data = defaultdict(list)
        for v in serializer.validated_data:
            data[v['categoria']].append((v['opcion'], v['votos']))

        with transaction.atomic():
            for categoria, opcion_votos in data.items():
                mesa_categoria = get_object_or_404(MesaCategoria, mesa=mesa, categoria=categoria)
                carga = Carga.objects.create(
                    # Sabemos que el bot va a mandar sólo cargas parciales.
                    tipo=Carga.TIPOS.parcial, origen=Carga.SOURCES.telegram,
                    mesa_categoria=mesa_categoria, fiscal=request.user.fiscal
                )

                for opcion, votos in opcion_votos:
                    categoria_opcion = get_object_or_404(
                        CategoriaOpcion, categoria=categoria, opcion=opcion
                    )

                    VotoMesaReportado.objects.create(
                        carga=carga,
                        opcion=categoria_opcion.opcion,
                        votos=votos
                    )

        # TODO: se deberían devolver los recursos creados
        return Response({"mensaje": "Se cargaron los votos con éxito."}, status=201)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    query_serializer=ListarCategoriasQuerySerializer,
    responses={status.HTTP_200_OK: CategoriaSerializer(many=True)},
    tags=['Categorias']
)
@api_view(
    ['GET'],
)
def listar_categorias(request):
    """
    Permite listar las categorías de la elección

    Se listan todas las categorías con prioridad menor o igual un valor dado.
    Por defecto se listan sólo categorias principales y secundarias (`prioridad=2`).
    Las categorias se ordenan primero por prioridad ascendente y luego alfabeticamente.
    """
    serializer = ListarCategoriasQuerySerializer(data=request.query_params)
    if serializer.is_valid():
        data = serializer.validated_data
        categorias = Categoria.objects.filter(prioridad__lte=data['prioridad']
                                              ).order_by('prioridad', 'nombre')
        return Response(CategoriaSerializer(categorias, many=True).data)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    query_serializer=ListarOpcionesQuerySerializer,
    responses={status.HTTP_200_OK: OpcionSerializer(many=True)},
    tags=['Opciones']
)
@api_view(
    ['GET'],
)
def listar_opciones(request, id_categoria):
    """
    Permite listar las opciones por categorías. No envía las opciones de metadata optativas.

    Por defecto se listan sólo las opciones prioritarias (`solo_prioritarias=true`).
    Las opciones se ordenan de forma ascendente según el campo orden (orden en el acta).
    """
    c = get_object_or_404(Categoria, id=id_categoria)
    serializer = ListarOpcionesQuerySerializer(data=request.query_params)
    if serializer.is_valid():
        opciones = c.opciones_actuales(**serializer.validated_data)
        return Response(OpcionSerializer(opciones, many=True).data)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
