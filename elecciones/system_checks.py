from django.core.checks import Error, register
from elecciones.models import Partido, Opcion, Categoria, Mesa, Circuito, LugarVotacion
from django.conf import settings
from django.db.models import F


@register(deploy=True)
def opciones_metadata(app_configs, **kwargs):
    """
    Chequea que existan las opciones de metadata necesarias para los cómputos parciales
    en todas las categorías.
    """
    errors = []
    opciones_metadata = [settings.OPCION_NULOS,
                         settings.OPCION_NULOS,
                         settings.OPCION_TOTAL_VOTOS,
                         settings.OPCION_TOTAL_SOBRES
    ]
    # Deben existir las opciones.
    for opcion_metadata in opciones_metadata:
        try:
            opcion = Opcion.objects.get(**opcion_metadata)
        except Opcion.DoesNotExist:
            nombre = opcion_metadata['nombre']
            errors.append(
                Error(
                    f'La opción {nombre} no está definida en la BD, o '
                    'está pero no correctamente.',
                    hint='Verificar que las opciones definidas en settings estén en la BD.',
                    obj=opcion_metadata,
                    id='elecciones.E001',
                )
            )

    # Deben estar en todas las categorías.
    categorias = Categoria.objects.filter(activa=True)
    for categoria in categorias:
        try:
            opcion_buscada = settings.OPCION_TOTAL_VOTOS['nombre']
            categoria.get_opcion_total_votos()
            opcion_buscada = settings.OPCION_NULOS['nombre']
            categoria.get_opcion_nulos()
            opcion_buscada = settings.OPCION_TOTAL_SOBRES['nombre']
            categoria.get_opcion_total_sobres()
            opcion_buscada = settings.OPCION_BLANCOS['nombre']
            categoria.get_opcion_blancos()
        except Opcion.DoesNotExist:
            errors.append(
                Error(
                    f'La opción {opcion_buscada} no está definida en la categoría '
                    f'{categoria.nombre}.',
                    hint='Crear la CategoriaOpcion necesaria.',
                    obj=categoria,
                    id='elecciones.E002',
                )
            )
    return errors

@register(deploy=True)
def partidos_ok(app_configs, **kwargs):
    """
    Chequea que los partidos estén bien definidos.
    """
    errors = []
    partidos = Partido.objects.all()

    for partido in partidos:
        if not partido.nombre_corto or not partido.nombre:
            errors.append(
                Error(
                    f'El partido {partido} no tiene definidos ambos nombres.',
                    hint='Chequear nombre y nombre_corto.',
                    obj=partido,
                    id='elecciones.E011',
                )
            )
        if not partido.codigo:
            errors.append(
                Error(
                    f'El partido {partido} no tiene definido su código.',
                    hint='Chequear código.',
                    obj=partido,
                    id='elecciones.E012',
                )
            )

        if partido.opciones.count() == 0:
            errors.append(
                Error(
                    f'El partido {partido} no tiene opciones definidas.',
                    hint='Chequear que existan opciones asociadas al partido.',
                    obj=partido,
                    id='elecciones.E0013',
                )
            )
        else:
            for opcion in partido.opciones.all():
                if opcion.tipo != Opcion.TIPOS.positivo:
                    errors.append(
                        Error(
                            f'El partido {partido} está asociado a la opción {opcion} '
                            'que no es positiva',
                            hint='Las opciones asociadas a partidos deben ser positivas.',
                            obj=opcion,
                            id='elecciones.E0014',
                        )
                    )
    return errors


@register(deploy=True)
def opciones_positivas_ok(app_configs, **kwargs):
    """
    Chequea que las opciones positivas tengan partido y estén bien definidas.
    """
    errors = []
    opciones = Opcion.objects.filter(tipo=Opcion.TIPOS.positivo)

    for opcion in opciones:
        if not opcion.nombre_corto or not opcion.nombre:
            errors.append(
                Error(
                    f'La opción {opcion} no tiene definidos ambos nombres.',
                    hint='Chequear nombre y nombre_corto.',
                    obj=opcion,
                    id='elecciones.E021',
                )
            )
        if not opcion.codigo:
            errors.append(
                Error(
                    f'La opción {opcion} no tiene definido su código.',
                    hint='Chequear código.',
                    obj=opcion,
                    id='elecciones.E022',
                )
            )

        if not opcion.partido:
            errors.append(
                Error(
                    f'La opción {opcion} no está asociada a un partido.',
                    hint='Las opciones positivas deben estar asociadas a un partido.',
                    obj=opcion,
                    id='elecciones.E023',
                )
            )
    return errors


@register(deploy=True)
def mesas_circuitos_lugares_vot_ok(app_configs, **kwargs):
    """
    Chequea que los lugares de votación a los que corresponden las mesas estén en su mismo circuito.
    """
    errors = []
    mesas_no_ok = Mesa.objects.filter(lugar_votacion__circuito=F('circuito'))

    for mesa in mesas_no_ok:
        errors.append(
            Error(
                f'La mesa {mesa} del circuito {mesa.circuito} está asociada al '
                'lugar de votación {mesa.lugar_votacion} que está en otro circuito.',
                hint='Chequear o bien la mesa o bien el lugar de votación.',
                obj=mesa,
                id='elecciones.E031',
            )
        )

    return errors
