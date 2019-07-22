from elecciones.tests.factories import UserFactory, FiscalFactory
from elecciones.tests.test_resultados import fiscal_client, setup_groups
from django.contrib.auth.models import Group


def test_esta_en_algun_grupo(db, setup_groups, admin_user):
    admin = FiscalFactory(user=admin_user)
    assert admin.esta_en_algun_grupo(('validadores', ))
    assert admin.esta_en_algun_grupo(('validadores', 'unidades basicas'))


def test_esta_en_algun_grupo__uno_de_dos(db, setup_groups):
    u_visualizador = UserFactory()
    visualizador = FiscalFactory(user=u_visualizador)
    g_visualizadores = Group.objects.get(name='visualizadores')
    u_visualizador.groups.add(g_visualizadores)

    assert visualizador.esta_en_algun_grupo(('visualizadores', ))
    assert not visualizador.esta_en_algun_grupo(('unidades basicas', ))
    assert visualizador.esta_en_algun_grupo(('unidades basicas', 'visualizadores'))


def test_esta_en_algun_grupo__ninguno(db, setup_groups):
    u_visualizador = UserFactory()
    visualizador = FiscalFactory(user=u_visualizador)
    g_visualizadores = Group.objects.get(name='visualizadores')
    g_visualizadores = Group.objects.get(name='validadores')
    u_visualizador.groups.add(g_visualizadores)

    assert not visualizador.esta_en_algun_grupo(('unidades basicas', 'supervisores'))


def test_esta_en_algun_grupo__grupo_no_existente(db, setup_groups):
    u_visualizador = UserFactory()
    visualizador = FiscalFactory(user=u_visualizador)
    g_visualizadores = Group.objects.get(name='visualizadores')
    g_visualizadores = Group.objects.get(name='validadores')
    u_visualizador.groups.add(g_visualizadores)

    assert visualizador.esta_en_algun_grupo(('grupo_no_existente', 'validadores'))
