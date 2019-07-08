import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from elecciones.tests import factories


def test_crear_carga(db, admin_user):
    """
    """
    url = reverse('crear-carga', kwargs={'mesa': 1, 'categoria': 1})
    data = {}

    # Esto es temporal hasta que se defina el mecanismo de autenticación de la API.
    client = APIClient()
    client.login(username='admin', password='password')
    response = client.post(url, data, format='json')
    client.logout()

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['mensaje'] == 'Carga creada con éxito.'
    

def test_importar_cargas(db, admin_user):
    """
    """
    url = reverse('importar-cargas')
    data = {}

    # Esto es temporal hasta que se defina el mecanismo de autenticación de la API.
    client = APIClient()
    client.login(username='admin', password='password')
    response = client.post(url, data, format='json')
    client.logout()

    assert response.status_code == status.HTTP_200_OK
    assert response.data['mensaje'] == 'Se importaron N actas con éxito.'
