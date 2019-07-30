from elecciones.tests.factories import (
    AttachmentFactory,
    CargaFactory,
    MesaFactory,
    MesaCategoriaFactory,
)
from django.urls import reverse
from elecciones.tests.test_resultados import fiscal_client, setup_groups # noqa
from http import HTTPStatus
from adjuntos.models import Attachment, Identificacion
from adjuntos.consolidacion import consumir_novedades_carga
from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
import os

def test_identificacion_create_view_get(fiscal_client, admin_user):
    a = AttachmentFactory()
    # se la asigno al fiscal
    a.take(admin_user.fiscal)

    response = fiscal_client.get(reverse('asignar-mesa', args=[a.id]))
    foto_url = a.foto.thumbnail['960x'].url
    assert response.status_code == HTTPStatus.OK
    assert foto_url in response.content.decode('utf8')


def test_identificacion_create_view_post(fiscal_client, admin_user):
    m1 = MesaFactory()
    a = AttachmentFactory()
    a.take(admin_user.fiscal)
    data = {
        'mesa': m1.id,
        'circuito': m1.circuito.id,
        'seccion': m1.circuito.seccion.id,
        'distrito': m1.circuito.seccion.distrito.id,
    }
    response = fiscal_client.post(reverse('asignar-mesa', args=[a.id]), data)
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('siguiente-accion')
    assert a.identificaciones.count() == 1
    i = a.identificaciones.first()
    assert i.status == Identificacion.STATUS.identificada
    assert i.mesa == m1
    assert i.fiscal == admin_user.fiscal
    # la identificacion todavia no está consolidada
    a.refresh_from_db()
    assert a.identificacion_testigo is None
    assert not m1.attachments.exists()


def test_identificacion_create_view_get__desde_unidad_basica(fiscal_client, admin_user):
    a = AttachmentFactory()
    a.take(admin_user.fiscal)
    response = fiscal_client.get(reverse('asignar-mesa-ub', args=[a.id]))
    assert response.status_code == HTTPStatus.OK

    foto_url = a.foto.thumbnail['960x'].url
    assert foto_url in response.content.decode('utf8')


def test_identificacion_create_view_post__desde_unidad_basica(fiscal_client, admin_user):
    mesa_1 = MesaFactory()
    attachment = AttachmentFactory()
    attachment.take(admin_user.fiscal)
    data = {
        'mesa': mesa_1.id,
        'circuito': mesa_1.circuito.id,
        'seccion': mesa_1.circuito.seccion.id,
        'distrito': mesa_1.circuito.seccion.distrito.id,
    }
    response = fiscal_client.post(reverse('asignar-mesa-ub', args=[attachment.id]), data)
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('procesar-acta-mesa', kwargs={'mesa_id': mesa_1.id})

    #refrescamos el attachment desde la base
    attachment.refresh_from_db()

    assert attachment.identificaciones.count() == 1
    assert attachment.status == Attachment.STATUS.identificada

    identificacion = attachment.identificaciones.first()
    assert attachment.identificacion_testigo == identificacion
    assert identificacion.status == Identificacion.STATUS.identificada
    assert identificacion.source == Identificacion.SOURCES.csv
    assert identificacion.mesa == mesa_1
    # la identificacion está consolidada, por lo tanto ya existe en la mesa
    assert mesa_1.attachments.exists()


def test_identificacion_problema_create_view_post(fiscal_client, admin_user):
    m1 = MesaFactory()
    a = AttachmentFactory()
    data = {
        'status': 'problema',
        'tipo_de_problema': 'invalida',
        'descripcion': 'Un problema'
    }
    response = fiscal_client.post(reverse('asignar-problema', args=[a.id]), data)
    assert response.status_code == 302
    assert response.url == reverse('siguiente-accion')
    assert a.identificaciones.count() == 1
    i = a.identificaciones.first()
    assert i.status == 'problema'
    assert i.fiscal == admin_user.fiscal
    assert i.mesa is None
    # mesa no tiene attach aun
    a.refresh_from_db()
    assert a.identificacion_testigo is None
    assert not m1.attachments.exists()


def test_identificacion_sin_permiso(fiscal_client, admin_user, mocker):
    fiscal = admin_user.fiscal
    capture = mocker.patch('adjuntos.views.capture_message')
    a = AttachmentFactory()
    response = fiscal_client.get(reverse('asignar-mesa', args=[a.id]))
    assert response.status_code == 403
    assert capture.call_count == 1
    mensaje = capture.call_args[0][0]
    assert 'Intento de asignar mesa de attachment' in mensaje
    assert str(fiscal) in mensaje
    a.take(fiscal)
    response = fiscal_client.get(reverse('asignar-mesa', args=[a.id]))
    assert response.status_code == 200

def test_preidentificacion_create_view_post(fiscal_client):
    content = open('adjuntos/tests/acta.jpg','rb')
    file = SimpleUploadedFile('acta.jpg', content.read(), content_type="image/jpeg")

    mesa_1 = MesaFactory()
    data = {
        'file_field': (file,),
        'circuito': mesa_1.circuito.id,
        'seccion': mesa_1.circuito.seccion.id,
        'distrito': mesa_1.circuito.seccion.distrito.id,
    }
    response = fiscal_client.post(reverse('agregar-adjuntos'), data)
    assert response.status_code == HTTPStatus.OK

    attachment = Attachment.objects.all().first()

    assert attachment.pre_identificacion is not None
    assert attachment.status == Attachment.STATUS.sin_identificar

    pre_identificacion = attachment.pre_identificacion
    assert pre_identificacion.circuito == mesa_1.circuito
    assert pre_identificacion.seccion == mesa_1.circuito.seccion
    assert pre_identificacion.distrito == mesa_1.circuito.seccion.distrito


def test_preidentificacion_sin_datos(fiscal_client):
    content = open('adjuntos/tests/acta.jpg','rb')
    file = SimpleUploadedFile('acta.jpg', content.read(), content_type="image/jpeg")

    mesa_1 = MesaFactory()
    data = {
        'file_field': (file,),
    }
    response = fiscal_client.post(reverse('agregar-adjuntos'), data)
    assert response.status_code == HTTPStatus.OK
    
    attachment = Attachment.objects.all().first()
    assert attachment is None
    assert "Este campo es requerido" in response.content.decode('utf8')


def test_preidentificacion_con_datos_de_fiscal(fiscal_client):
    content = open('adjuntos/tests/acta.jpg','rb')
    mesa = MesaFactory()
    seccion = mesa.circuito.seccion

    form_response = fiscal_client.get(reverse('agregar-adjuntos'))
    fiscal = form_response.wsgi_request.user.fiscal
    fiscal.seccion = seccion
    fiscal.save()
    fiscal.refresh_from_db()

    distrito_preset = f"presetOption('id_distrito','{seccion.distrito}','{seccion.distrito.id}');"
    seccion_preset =  f"presetOption('id_seccion','{seccion}','{seccion.id}');"

    response = fiscal_client.get(reverse('agregar-adjuntos'))
    content = response.content.decode('utf8')

    assert distrito_preset in content
    assert seccion_preset in content
