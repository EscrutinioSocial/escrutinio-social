from django.conf import settings
from django.core.checks import Error, register, Warning, Tags
from django.db.models import F, Sum
from elecciones.models import (
    Categoria,
    Circuito,
    Distrito,
    LugarVotacion,
    Mesa,
    Opcion,
    Partido,
    Seccion,
)


@register(Tags.models, deploy=True)
def opciones_metadata(app_configs, **kwargs):
    """
    Chequea que existan las opciones de metadata necesarias para los cómputos parciales
    en todas las categorías.
    """
    errors = []
    opciones_en_settings = [
        'OPCION_NULOS',
        'OPCION_BLANCOS',
        'OPCION_TOTAL_VOTOS',
        'OPCION_TOTAL_SOBRES',
        'OPCION_RECURRIDOS',
        'OPCION_ID_IMPUGNADA',
        'OPCION_COMANDO_ELECTORAL',
    ]
    # Deben existir las opciones en la base
    for opcion_setting in opciones_en_settings:
        try:
            opcion = Opcion.objects.get(**getattr(settings, opcion_setting))
        except Opcion.DoesNotExist:
            errors.append(
                Error(
                    f'La opción definida en {opcion_setting} no existe en la BD, o '
                    'está pero no correctamente.',
                    hint='Verificar que las opciones definidas en settings estén en la BD.',
                    obj=opcion_setting,
                    id='elecciones.E001',
                )
            )
        else:
            for categoria in Categoria.objects.exclude(opciones=opcion):
                errors.append(
                    Error(
                        f'La opción {opcion.nombre} no está asociada a la categoría '
                        f'{categoria.nombre}.',
                        hint='Crear la CategoriaOpcion necesaria.',
                        obj=categoria,
                        id='elecciones.E002',
                    )
                )
    return errors


@register(Tags.models, deploy=True)
def partidos_ok(app_configs, **kwargs):
    """
    Chequea que los partidos estén bien definidos.
    """
    errors = []
    partidos = Partido.objects.all()

    for partido in partidos:
        if not partido.nombre_corto or not partido.nombre:
            errors.append(
                Warning(
                    f'El partido {partido} no tiene definidos ambos nombres.',
                    hint='Chequear nombre y nombre_corto.',
                    obj=partido,
                    id='elecciones.E011',
                )
            )
        if not partido.codigo:
            errors.append(
                Warning(
                    f'El partido {partido} no tiene definido su código.',
                    hint='Chequear código.',
                    obj=partido,
                    id='elecciones.E012',
                )
            )
        if not partido.opciones.exists():
            errors.append(
                Error(
                    f'El partido {partido} no tiene opciones definidas.',
                    hint='Chequear que existan opciones asociadas al partido.',
                    obj=partido,
                    id='elecciones.E0013',
                )
            )
        else:
            for opcion in partido.opciones.exclude(tipo=Opcion.TIPOS.positivo):
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


@register(Tags.models, deploy=True)
def opciones_positivas_ok(app_configs, **kwargs):
    """
    Chequea que las opciones positivas tengan partido y estén bien definidas.
    """
    errors = []
    for opcion in Opcion.objects.filter(tipo=Opcion.TIPOS.positivo):
        if not opcion.nombre_corto or not opcion.nombre:
            errors.append(
                Warning(
                    f'La opción {opcion} no tiene definidos ambos nombres.',
                    hint='Chequear nombre y nombre_corto.',
                    obj=opcion,
                    id='elecciones.E021',
                )
            )
        if not opcion.codigo:
            errors.append(
                Warning(
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


@register(Tags.models, deploy=True)
def mesas_circuitos_lugares_vot_ok(app_configs, **kwargs):
    """
    Chequea que los lugares de votación a los que corresponden las mesas estén en su mismo circuito.
    """
    errors = []
    mesas_no_ok = Mesa.objects.exclude(lugar_votacion__circuito=F('circuito'))

    for mesa in mesas_no_ok:
        errors.append(
            Error(
                f'La mesa {mesa} del circuito {mesa.circuito} está asociada al '
                f'lugar de votación {mesa.lugar_votacion} que está en otro circuito.',
                hint='Chequear o bien la mesa o bien el lugar de votación.',
                obj=mesa,
                id='elecciones.E031',
            )
        )

    return errors


@register(Tags.models, deploy=True)
def mesas_electores(app_configs, **kwargs):
    """
    Chequea que los lugares de votación a los que corresponden las mesas estén en su mismo circuito.
    """

    errors = []
    for d in Distrito.objects.all():
        if d.electores is not None and d.electores != d.secciones.aggregate(v=Sum('electores'))['v']:
            errors.append(
                Error(
                    f'Los electores del distrito {d} no coinciden con la suma '
                    'de los electores de sus secciones',
                )
            )

    for s in Seccion.objects.all():
        if s.electores is not None and s.electores != s.circuitos.aggregate(v=Sum('electores'))['v']:
            errors.append(
                Error(
                    f'Los electores de la sección {s} no coinciden con la suma '
                    'de los electores de sus circuitos',
                )
            )

    for c in Circuito.objects.all():
        if c.electores is not None and c.electores != c.lugares_votacion.aggregate(v=Sum('electores'))['v']:
            errors.append(
                Error(
                    f'Los electores del circuito {c} no coinciden con la suma '
                    'de los electores de sus lugares de votacion',
                )
            )

    for l in LugarVotacion.objects.all():
        if l.electores is not None and l.electores != l.mesas.aggregate(v=Sum('electores'))['v']:
            errors.append(
                Error(
                    f'Los electores de {l} no coinciden con la suma '
                    'de los electores de sus mesas',
                )
            )
    return errors


@register(Tags.models, deploy=True)
def categorias_ok(app_configs, **kwargs):
    """
    Chequea que la información geográfica de las categorías concida con las mesas que tienen asociadas.
    """
    errors = []

    # Categorías asociadas a distrito.
    for categoria in Categoria.objects.filter(activa=True, distrito__isnull=False):
        mesas = Mesa.objects.filter(
            lugar_votacion__circuito__seccion__distrito=categoria.distrito
        ).exclude(
            circuito__seccion__distrito=categoria.distrito
        )

        if mesas.exists():
            errors.append(
                Error(
                    f'La categoria {categoria} está asociada al distrito {categoria.distrito} '
                    f'pero tiene mesas en otros distritos ({mesas}).',
                    hint='Chequear o bien las mesas o bien el distrito de la categoria.',
                    obj=categoria,
                    id='elecciones.E051',
                )
            )

    # Categorías asociadas a sección.
    for categoria in Categoria.objects.filter(activa=True, seccion__isnull=False):
        mesas = Mesa.objects.filter(
            lugar_votacion__circuito__seccion=categoria.seccion
        ).exclude(
            circuito__seccion=categoria.seccion
        )

        if mesas.exists():
            errors.append(
                Error(
                    f'La categoria {categoria} está asociada a la sección {categoria.seccion} '
                    f'pero tiene mesas en otras secciones ({mesas}).',
                    hint='Chequear o bien las mesas o bien la sección de la categoria.',
                    obj=categoria,
                    id='elecciones.E051',
                )
            )

    return errors
