import io
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from elecciones.tests import factories
from adjuntos.models import hash_file
from elecciones.models import Mesa, Opcion, Categoria, CategoriaOpcion


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


def test_listar_categorias_default(admin_client):
    url = reverse('categorias')
    
    pv = factories.CategoriaFactory(prioridad=1)
    gv = factories.CategoriaFactory(prioridad=2)
    dn = factories.CategoriaFactory(prioridad=3)

    response = admin_client.get(url, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2
    assert [cat['id'] for cat in response.data] == [pv.id, gv.id]


def test_listar_categorias_con_prioridad(admin_client):
    url = reverse('categorias')
    
    pv = factories.CategoriaFactory(prioridad=1)
    gv = factories.CategoriaFactory(prioridad=2)
    dn = factories.CategoriaFactory(prioridad=3)
    lp = factories.CategoriaFactory(prioridad=4)

    response = admin_client.get(url, data={'prioridad': 3}, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 3
    assert [
        (cat['id'], cat['nombre']) for cat in response.data
    ] == [
        (pv.id, pv.nombre),
        (gv.id, gv.nombre),
        (dn.id, dn.nombre)
    ]
    

def test_listar_opciones_default(admin_client):
    o2 = factories.OpcionFactory(orden=3)
    o3 = factories.OpcionFactory(orden=2)
    
    c = factories.CategoriaFactory(opciones=[o2, o3])
    
    o1 = factories.CategoriaOpcionFactory(categoria=c, opcion__orden=1, prioritaria=True).opcion
    o4 = factories.CategoriaOpcionFactory(categoria=c, opcion__orden=4, prioritaria=True).opcion

    url = reverse('opciones', kwargs={'id_categoria': c.id})
    
    response = admin_client.get(url, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2
    assert [
        (opc['id'], opc['nombre']) for opc in response.data
    ] == [
        (o1.id, o1.nombre),
        (o4.id, o4.nombre)
    ]

def test_listar_opciones_todas(admin_client):
    o2 = factories.OpcionFactory(orden=3)
    o3 = factories.OpcionFactory(orden=2)
    
    c = factories.CategoriaFactory(opciones=[o2, o3])
    
    o1 = factories.CategoriaOpcionFactory(categoria=c, opcion__orden=1, prioritaria=True).opcion
    o4 = factories.CategoriaOpcionFactory(categoria=c, opcion__orden=4, prioritaria=True).opcion

    url = reverse('opciones', kwargs={'id_categoria': c.id})
    
    response = admin_client.get(url, data={'solo_prioritarias': False}, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 4
    assert [
        (opc['id'], opc['nombre']) for opc in response.data
    ] == [
        (o1.id, o1.nombre),
        (o3.id, o3.nombre),
        (o2.id, o2.nombre),
        (o4.id, o4.nombre),
    ]


