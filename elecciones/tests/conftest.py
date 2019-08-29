import pytest
from django.urls import reverse
from django.contrib.auth.models import Group

from .factories import (CategoriaFactory, FiscalFactory)
from .utils import create_carta_marina


@pytest.fixture()
def carta_marina(db):
    return create_carta_marina()


@pytest.fixture()
def setup_groups(db, admin_user):
    groups = [
        'validadores', 'unidades basicas', 'visualizadores', 'supervisores', 'fiscales con acceso al bot',
        'visualizadores_sensible'
    ]
    for nombre in groups:
        g = Group.objects.create(name=nombre)
        admin_user.groups.add(g)


@pytest.fixture()
def fiscal_client(db, admin_user, setup_groups, client):
    """A Django test client logged in as an admin user."""
    FiscalFactory(user=admin_user)
    client.login(username=admin_user.username, password='password')
    return client

def fiscal_client_from_fiscal(client, fiscal):
    """
    Debe ser llamado desde un test que previamente llame al fixture setup_groups.
    """
    g = Group.objects.get(name='validadores')
    fiscal.user.groups.add(g)
    client.login(username=fiscal.user.username, password='password')
    return client

@pytest.fixture()
def url_resultados(carta_marina):
    c = CategoriaFactory(nombre='default')
    return reverse('resultados-categoria', args=[c.id])


@pytest.fixture()
def url_resultados_computo(carta_marina):
    c = CategoriaFactory(nombre='default')
    return reverse('resultados-en-base-a-configuración', args=[c.id])
