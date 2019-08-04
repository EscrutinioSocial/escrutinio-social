import pytest

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from elecciones.tests import factories
from elecciones.models import Carga
from adjuntos.models import Attachment, hash_file

from elecciones.tests.factories import (
    DistritoFactory,
    SeccionFactory
)

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

    foto = (datadir / 'acta.jpeg')
    response = admin_client.post(url, {'foto': foto.open('rb')})

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['foto_digest'] == hash_file(foto.open('rb'))

    response = admin_client.post(url, {'foto': foto.open('rb')})

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data['foto_digest'] == hash_file(foto.open('rb'))

def test_subir_acta_preidentifica_distrito(admin_user, admin_client, datadir):
    """
    Prueba de subir una imagen y que quede la PreIdentificación de distrito.
    """
    url = reverse('actas')
    distrito = DistritoFactory()
    admin_user.fiscal.distrito = distrito
    admin_user.fiscal.save()

    foto = (datadir / 'acta.jpeg')
    response = admin_client.post(url, {'foto': foto.open('rb')})

    assert response.status_code == status.HTTP_201_CREATED

    response = admin_client.post(url, {'foto': foto.open('rb')})

    foto_digest = response.data['foto_digest']

    attachment = Attachment.objects.get(foto_digest=foto_digest)

    assert attachment.pre_identificacion is not None
    assert attachment.pre_identificacion.distrito == admin_user.fiscal.distrito

def test_subir_acta_preidentifica_seccion(admin_user, admin_client, datadir):
    """
    Prueba de subir una imagen y que quede la PreIdentificación de seccion
    """
    url = reverse('actas')
    seccion = SeccionFactory()
    admin_user.fiscal.seccion = seccion
    admin_user.fiscal.save()

    foto = (datadir / 'acta.jpeg')
    response = admin_client.post(url, {'foto': foto.open('rb')})

    assert response.status_code == status.HTTP_201_CREATED

    response = admin_client.post(url, {'foto': foto.open('rb')})

    foto_digest = response.data['foto_digest']

    attachment = Attachment.objects.get(foto_digest=foto_digest)

    assert attachment.pre_identificacion is not None
    assert attachment.pre_identificacion.seccion == admin_user.fiscal.seccion
    assert attachment.pre_identificacion.distrito == admin_user.fiscal.seccion.distrito

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


def test_identificar_acta_error(admin_client):
    """
    """
    attachment = factories.AttachmentFactory()
    assert attachment.identificaciones.count() == 0

    url = reverse('identificar-acta', kwargs={'foto_digest': attachment.foto_digest})

    response = admin_client.put(url, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


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

    categoria_1 = factories.CategoriaFactory()
    categoria_2 = factories.CategoriaFactory()

    mesa_categoria_1 = factories.MesaCategoriaFactory(mesa=mesa, categoria=categoria_1)
    mesa_categoria_2 = factories.MesaCategoriaFactory(mesa=mesa, categoria=categoria_2)

    opcion_1 = factories.OpcionFactory(orden=1)
    opcion_2 = factories.OpcionFactory(orden=2)

    factories.CategoriaOpcionFactory(categoria=categoria_1, opcion=opcion_1, prioritaria=True)
    factories.CategoriaOpcionFactory(categoria=categoria_1, opcion=opcion_2, prioritaria=True)
    factories.CategoriaOpcionFactory(categoria=categoria_2, opcion=opcion_1, prioritaria=True)

    data = [{
        'categoria': categoria_1.id,
        'opcion': opcion_1.id,
        'votos': 100
    }, {
        'categoria': categoria_1.id,
        'opcion': opcion_2.id,
        'votos': 50
    }, {
        'categoria': categoria_2.id,
        'opcion': opcion_1.id,
        'votos': 10
    }]

    response = admin_client.post(url, data, format='json')

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['mensaje'] == 'Se cargaron los votos con éxito.'

    assert Carga.objects.count() == 2
    assert mesa_categoria_1.cargas.count() == 1
    assert mesa_categoria_2.cargas.count() == 1

    assert [
        list(mc.opcion_votos().order_by('opcion__orden'))
        for mc in mesa_categoria_1.cargas.order_by('-created').all()
    ] == [
        [(opcion_1.id, 100), (opcion_2.id, 50)]
    ]

    assert [
        list(mc.opcion_votos().order_by('opcion__orden'))
        for mc in mesa_categoria_2.cargas.order_by('-created').all()
    ] == [
        [(opcion_1.id, 10)]
    ]

    # Se pueden volver a cargar votos para la misma mesa (con o sin cambios)

    data[0]['votos'] = 90
    data[1]['votos'] = 60
    response = admin_client.post(url, data, format='json')

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['mensaje'] == 'Se cargaron los votos con éxito.'

    assert Carga.objects.count() == 4
    assert mesa_categoria_1.cargas.count() == 2
    assert mesa_categoria_2.cargas.count() == 2

    assert [
        list(mc.opcion_votos().order_by('opcion__orden'))
        for mc in mesa_categoria_1.cargas.order_by('-created').all()
    ] == [
        [(opcion_1.id, 90), (opcion_2.id, 60)],
        [(opcion_1.id, 100), (opcion_2.id, 50)]
    ]

    assert [
        list(mc.opcion_votos().order_by('opcion__orden'))
        for mc in mesa_categoria_2.cargas.order_by('-created').all()
    ] == [
        [(opcion_1.id, 10)],
        [(opcion_1.id, 10)]
    ]


def test_cargar_votos_faltan_prioritarias(admin_client):
    """
    """
    mesa = factories.MesaFactory()
    url = reverse('cargar-votos', kwargs={'id_mesa': mesa.id})

    categoria_1 = factories.CategoriaFactory()
    categoria_2 = factories.CategoriaFactory()

    opcion_1 = factories.OpcionFactory()
    opcion_2 = factories.OpcionFactory()

    factories.CategoriaOpcionFactory(categoria=categoria_1, opcion=opcion_1, prioritaria=True)
    factories.CategoriaOpcionFactory(categoria=categoria_1, opcion=opcion_2, prioritaria=True)
    factories.CategoriaOpcionFactory(categoria=categoria_2, opcion=opcion_1, prioritaria=True)

    data = [{
        'categoria': categoria_1.id,
        'opcion': opcion_1.id,
        'votos': 100
    }, {
        'categoria': categoria_2.id,
        'opcion': opcion_1.id,
        'votos': 10
    }]

    response = admin_client.post(url, data, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data['non_field_errors'][0].code == 'invalid'


def test_listar_categorias_default(admin_client):
    url = reverse('categorias')

    gv = factories.CategoriaFactory(prioridad=2)
    pv = factories.CategoriaFactory(prioridad=1)
    factories.CategoriaFactory(prioridad=3)

    response = admin_client.get(url, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2
    categorias = [(cat['id'], cat['nombre'], cat['slug']) for cat in response.data]
    assert categorias == [
        (pv.id, pv.nombre, pv.slug),
        (gv.id, gv.nombre, gv.slug)
    ]


def test_listar_categorias_con_prioridad(admin_client):
    url = reverse('categorias')

    gv = factories.CategoriaFactory(prioridad=2)
    pv = factories.CategoriaFactory(prioridad=1)
    dn = factories.CategoriaFactory(prioridad=3)
    factories.CategoriaFactory(prioridad=4)

    response = admin_client.get(url, data={'prioridad': 3}, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 3
    categorias = [(cat['id'], cat['nombre'], cat['slug']) for cat in response.data]
    assert categorias == [
        (pv.id, pv.nombre, pv.slug),
        (gv.id, gv.nombre, gv.slug),
        (dn.id, dn.nombre, dn.slug)
    ]


@pytest.mark.parametrize('prioridad', ['XX', False])
def test_listar_categorias_con_prioridad_error(prioridad, admin_client):
    url = reverse('categorias')

    response = admin_client.get(url, data={'prioridad': prioridad}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


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

    opciones = [(opc['id'], opc['nombre'], opc['nombre_corto'], opc['codigo']) for opc in response.data]
    assert opciones == [
        (o1.id, o1.nombre, o1.nombre_corto, o1.codigo),
        (o4.id, o4.nombre, o4.nombre_corto, o4.codigo)
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

    opciones = [(opc['id'], opc['nombre'], opc['nombre_corto'], opc['codigo']) for opc in response.data]
    assert opciones == [
        (o1.id, o1.nombre, o1.nombre_corto, o1.codigo),
        (o3.id, o3.nombre, o3.nombre_corto, o3.codigo),
        (o2.id, o2.nombre, o2.nombre_corto, o2.codigo),
        (o4.id, o4.nombre, o4.nombre_corto, o4.codigo),
    ]


@pytest.mark.parametrize('valor', ['No booleano', 42])
def test_listar_opciones_error(valor, admin_client):
    c = factories.CategoriaFactory()
    url = reverse('opciones', kwargs={'id_categoria': c.id})

    response = admin_client.get(url, data={'solo_prioritarias': valor}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
