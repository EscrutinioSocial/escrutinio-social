import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from elecciones.tests import factories


def test_subir_acta(db, admin_user):
    """
    """
    url = reverse('actas')
    data = {}

    # Esto es temporal hasta que se defina el mecanismo de autenticación de la API.
    client = APIClient()
    client.login(username='admin', password='password')
    response = client.post(url, data)
    client.logout()

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['foto_digest'] == ''
    

def test_identificar_acta(db, admin_user):
    """
    """
    url = reverse('identificar-acta', kwargs={'foto_digest': '90554e1d519e0fc665fab042d7499'})
    data = {}

    # Esto es temporal hasta que se defina el mecanismo de autenticación de la API.
    client = APIClient()
    client.login(username='admin', password='password')
    response = client.put(url, data, format='json')
    client.logout()

    assert response.status_code == status.HTTP_200_OK
    assert response.data['mensaje'] == 'El acta fue identificada con éxito.'


def test_cargar_votos(db, admin_user):
    """
    """
    url = reverse('cargar-votos', kwargs={'foto_digest': '90554e1d519e0fc665fab042d7499'})
    data = {}

    # Esto es temporal hasta que se defina el mecanismo de autenticación de la API.
    client = APIClient()
    client.login(username='admin', password='password')
    response = client.post(url, data, format='json')
    client.logout()

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['mensaje'] == 'Se cargaron los votos con éxito.'


def test_listar_categorias(db, admin_user):
    url = reverse('categorias')
    
    # Esto es temporal hasta que se defina el mecanismo de autenticación de la API.
    client = APIClient()
    client.login(username='admin', password='password')
    response = client.get(url, format='json')
    client.logout()

    assert response.status_code == status.HTTP_200_OK
    assert response.data == []


def test_listar_opciones(db, admin_user):
    url = reverse('opciones', kwargs={'id_categoria': 1})
    
    # Esto es temporal hasta que se defina el mecanismo de autenticación de la API.
    client = APIClient()
    client.login(username='admin', password='password')
    response = client.get(url, format='json')
    client.logout()

    assert response.status_code == status.HTTP_200_OK
    assert response.data == []
