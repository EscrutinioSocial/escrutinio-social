import io
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from elecciones.tests import factories
from adjuntos.models import hash_file


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    response = client.post('/api/token/', dict(username='admin', password='password'))
    client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['access'])

    return client
    

def test_subir_acta(admin_client, datadir):
    """
    Prueba exitosa de subir la imagen de un acta.
    """
    url = reverse('actas')

    with open(datadir / 'acta.jpeg', 'rb') as foto:
        response = admin_client.post(url, {'foto': foto})

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['foto_digest'] == hash_file(open(datadir / 'acta.jpeg', 'rb'))
    

def test_subir_acta_invalid_ext(admin_client, datadir):
    """
    Prueba que solo se aceptan archivos de imagenes.
    """
    url = reverse('actas')

    with open(datadir / 'acta.pdf', 'rb') as foto:
        response = admin_client.post(url, {'foto': foto})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data['foto'][0].code == 'invalid_image'
    

def test_identificar_acta(admin_client):
    """
    """
    url = reverse('identificar-acta', kwargs={'foto_digest': '90554e1d519e0fc665fab042d7499'})
    data = {}

    response = admin_client.put(url, data, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert response.data['mensaje'] == 'El acta fue identificada con éxito.'


def test_cargar_votos(admin_client):
    """
    """
    url = reverse('cargar-votos', kwargs={'foto_digest': '90554e1d519e0fc665fab042d7499'})
    data = {}

    response = admin_client.post(url, data, format='json')

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['mensaje'] == 'Se cargaron los votos con éxito.'


def test_listar_categorias(admin_client):
    url = reverse('categorias')
    
    response = admin_client.get(url, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert response.data == []


def test_listar_opciones(admin_client):
    url = reverse('opciones', kwargs={'id_categoria': 1})
    
    response = admin_client.get(url, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert response.data == []
