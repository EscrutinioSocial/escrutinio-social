from elecciones.tests.factories import CategoriaFactory
from elecciones.models import Opcion
from django.conf import settings
from django.core.management import call_command


def test_setup_opciones(db):
    assert not Opcion.objects.exists()
    c = CategoriaFactory(opciones=[])
    call_command('setup_opciones_basicas')
    assert Opcion.objects.get(**settings.OPCION_BLANCOS)
    assert Opcion.objects.get(**settings.OPCION_TOTAL_VOTOS)
    assert Opcion.objects.get(**settings.OPCION_TOTAL_SOBRES)
    assert Opcion.objects.get(**settings.OPCION_NULOS)
    assert Opcion.objects.get(**settings.OPCION_RECURRIDOS)
    assert Opcion.objects.get(**settings.OPCION_ID_IMPUGNADA)
    assert Opcion.objects.get(**settings.OPCION_COMANDO_ELECTORAL)
    assert c.opciones.count() == 7
