import io
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from elecciones.tests import factories
from adjuntos.models import hash_file
from elecciones.models import Mesa, Opcion, Categoria


@pytest.fixture
def admin_client(admin_user):
    """
    Cliente con el header Bearer <token> y autenticado como admin
    """
    factories.FiscalFactory(user=admin_user)

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
    mesa = factories.MesaFactory()

    codigo_distrito = mesa.circuito.seccion.distrito.numero
    codigo_seccion = mesa.circuito.seccion.numero
    codigo_circuito = mesa.circuito.numero
    codigo_mesa = mesa.numero

    attachment = factories.AttachmentFactory()
    assert attachment.identificaciones.count() == 0

    url = reverse('identificar-acta', kwargs={'foto_digest': attachment.foto_digest})
    data = {
        'codigo_distrito': codigo_distrito,
        'codigo_seccion': codigo_seccion,
        'codigo_circuito': codigo_circuito,
        'codigo_mesa': codigo_mesa
    }

    response = admin_client.put(url, data, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert attachment.identificaciones.count() == 1

    identificacion = attachment.identificaciones.first()

    assert response.data['id'] == identificacion.mesa.id
    assert identificacion.mesa.numero == codigo_mesa
    assert identificacion.mesa.circuito.numero == codigo_circuito
    assert identificacion.mesa.circuito.seccion.numero == codigo_seccion
    assert identificacion.mesa.circuito.seccion.distrito.numero == codigo_distrito


def test_identificar_acta_not_found(admin_client):
    """
    """
    url = reverse('identificar-acta', kwargs={'foto_digest': '90554e1d519e0fc665fab042d7499'})
    response = admin_client.put(url, format='json')

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_cargar_votos(admin_client):
    """
    """
    mesa = factories.MesaFactory()
    url = reverse('cargar-votos', kwargs={'id_mesa': mesa.id})

    categoria_opcion = factories.CategoriaOpcionFactory()
    data = [{
        'categoria': categoria_opcion.categoria.id,
        'opcion': categoria_opcion.opcion.id,
        'votos': 100
    }]

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
