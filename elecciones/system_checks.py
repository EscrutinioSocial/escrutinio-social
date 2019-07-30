from django.core.checks import Error, register

@register()
def opciones_metadata(app_configs, **kwargs):
    """
    Chequea que existan las opciones de metadata necesarias para los cómputos parciales.
    """
    errors = []
    opciones_metadata = [settings.OPCION_BLANCOS, 
        settings.OPCION_NULOS, 
        settings.OPCION_TOTAL_VOTOS, 
        settings.OPCION_TOTAL_SOBRES
    ]
    for opcion_metadata in opciones_metadata:
        try:
            opcion = Opcion.objects.get(**opcion_metadata)
        except Opcion.DoesNotExist:
            errors.append(
                Error(
                    f'La opción {opcion_metadata.nombre} no está definida en la BD, o '
                    'está pero no correctamente.',
                    hint='Verificar que las opciones definidas en settings estén en la BD.',
                    obj=opcion_metadata,
                    id='elecciones.E001',
                )
            )
    return errors