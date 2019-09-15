from elecciones.tests.factories import ( AttachmentFactory, MesaFactory, )
from django.urls import reverse
from elecciones.tests.conftest import fiscal_client, setup_groups # noqa
from http import HTTPStatus
from adjuntos.models import Attachment, Identificacion
from django.core.files.uploadedfile import SimpleUploadedFile


def test_identificacion_create_view_get(fiscal_client, admin_user):
    a = AttachmentFactory()
    # Se la asigno al fiscal
    admin_user.fiscal.asignar_attachment(a)

    response = fiscal_client.get(reverse('asignar-mesa', args=[a.id]))
    foto_url = a.foto.thumbnail['960x'].url
    assert response.status_code == HTTPStatus.OK
    assert foto_url in response.content.decode('utf8')

def test_identificacion_create_view_post(fiscal_client, admin_user):
    m1 = MesaFactory()
    a = AttachmentFactory()
    admin_user.fiscal.asignar_attachment(a)
    a.asignar_a_fiscal()
    data = {
        'mesa': m1.numero,
        'circuito': m1.circuito.numero,
        'seccion': m1.circuito.seccion.numero,
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
    # La identificación todavía no está consolidada.
    a.refresh_from_db()
    assert a.identificacion_testigo is None
    assert not m1.attachments.exists()
    assert a.cant_fiscales_asignados == 0


def test_identificacion_create_view_get__desde_unidad_basica(fiscal_client, admin_user):
    a = AttachmentFactory()
    admin_user.fiscal.asignar_attachment(a)
    a.asignar_a_fiscal()
    response = fiscal_client.get(reverse('asignar-mesa-ub', args=[a.id]))
    assert response.status_code == HTTPStatus.OK

    foto_url = a.foto.thumbnail['960x'].url
    assert foto_url in response.content.decode('utf8')


def test_identificacion_create_view_post__desde_unidad_basica(fiscal_client, admin_user):
    mesa_1 = MesaFactory()
    attachment = AttachmentFactory()
    admin_user.fiscal.asignar_attachment(attachment)
    attachment.asignar_a_fiscal()
    data = {
        'mesa': mesa_1.numero,
        'circuito': mesa_1.circuito.numero,
        'seccion': mesa_1.circuito.seccion.numero,
        'distrito': mesa_1.circuito.seccion.distrito.id,
    }
    response = fiscal_client.post(reverse('asignar-mesa-ub', args=[attachment.id]), data)
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('procesar-acta-mesa', kwargs={'mesa_id': mesa_1.id})

    # Refrescamos el attachment desde la base.
    attachment.refresh_from_db()

    assert attachment.identificaciones.count() == 1
    assert attachment.status == Attachment.STATUS.identificada

    identificacion = attachment.identificaciones.first()
    assert attachment.identificacion_testigo == identificacion
    assert identificacion.status == Identificacion.STATUS.identificada
    assert identificacion.source == Identificacion.SOURCES.csv
    assert identificacion.mesa == mesa_1
    # La identificación está consolidada, por lo tanto ya existe en la mesa
    assert mesa_1.attachments.exists()


def test_identificacion_problema_create_view_post_no_ajax(fiscal_client, mocker):
    info = mocker.patch('adjuntos.views.messages.info')
    a = AttachmentFactory()
    data = {
        'status': 'problema',
        'tipo_de_problema': 'falta_lista',
        'descripcion': 'Un problema'
    }
    # ajax post
    url = reverse('asignar-problema', args=[a.id])
    response = fiscal_client.post(url, data)
    assert response.status_code == 302
    assert info.call_args[0][1] == 'Gracias por el reporte. Ahora pasamos a la siguiente acta.'
    assert response.url == reverse('siguiente-accion')
    # estrictamente, acá no se crea ningun problema
    assert not a.problemas.exists()


def test_identificacion_problema_create_view_post_ajax(fiscal_client, admin_user):
    a = AttachmentFactory()
    data = {
        'status': 'problema',
        'tipo_de_problema': 'falta_lista',
        'descripcion': 'Un problema'
    }
    # ajax post
    url = reverse('asignar-problema', args=[a.id])
    response = fiscal_client.post(url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    assert response.status_code == 200
    # hack
    assert response.json() == {'status': 'hack'}

    assert a.identificaciones.count() == 1
    i = a.identificaciones.first()
    assert i.status == 'problema'
    assert i.fiscal == admin_user.fiscal
    assert i.mesa is None
    # mesa no tiene attach aun
    a.refresh_from_db()
    assert a.identificacion_testigo is None

    # hay un problema asociado al attach con un reporte asociado
    problema = a.problemas.get()                # demuestra que es 1 solo
    assert problema.estado == 'potencial'
    reporte = problema.reportes.get()           # idem, es 1 solo
    assert reporte.tipo_de_problema == 'falta_lista'
    assert reporte.reportado_por == admin_user.fiscal
    assert reporte.descripcion == 'Un problema'


def test_identificacion_sin_permiso(fiscal_client, admin_user, mocker):
    fiscal = admin_user.fiscal
    capture = mocker.patch('adjuntos.views.capture_message')
    a = AttachmentFactory()
    response = fiscal_client.get(reverse('asignar-mesa', args=[a.id]))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('siguiente-accion')
    assert capture.call_count == 1
    mensaje = capture.call_args[0][0]
    assert 'Intento de asignar mesa de attachment' in mensaje
    assert str(fiscal) in mensaje
    fiscal.asignar_attachment(a)
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

def test_preidentificacion_seccion_y_distrito_create_view_post(fiscal_client):
    content = open('adjuntos/tests/acta.jpg','rb')
    file = SimpleUploadedFile('acta.jpg', content.read(), content_type="image/jpeg")

    mesa_1 = MesaFactory()
    data = {
        'file_field': (file,),
        'seccion': mesa_1.circuito.seccion.id,
        'distrito': mesa_1.circuito.seccion.distrito.id,
    }
    response = fiscal_client.post(reverse('agregar-adjuntos'), data)
    assert response.status_code == HTTPStatus.OK

    attachment = Attachment.objects.all().first()

    assert attachment.pre_identificacion is not None
    assert attachment.status == Attachment.STATUS.sin_identificar

    pre_identificacion = attachment.pre_identificacion
    assert pre_identificacion.seccion == mesa_1.circuito.seccion
    assert pre_identificacion.distrito == mesa_1.circuito.seccion.distrito

def test_preidentificacion_solo_distrito_create_view_post(fiscal_client):
    content = open('adjuntos/tests/acta.jpg','rb')
    file = SimpleUploadedFile('acta.jpg', content.read(), content_type="image/jpeg")

    mesa_1 = MesaFactory()
    data = {
        'file_field': (file,),
        'distrito': mesa_1.circuito.seccion.distrito.id,
    }
    response = fiscal_client.post(reverse('agregar-adjuntos'), data)
    assert response.status_code == HTTPStatus.OK

    attachment = Attachment.objects.all().first()

    assert attachment.pre_identificacion is not None
    assert attachment.status == Attachment.STATUS.sin_identificar

    pre_identificacion = attachment.pre_identificacion
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
    mesa = MesaFactory()
    seccion = mesa.circuito.seccion

    form_response = fiscal_client.get(reverse('agregar-adjuntos'))
    fiscal = form_response.wsgi_request.user.fiscal
    fiscal.seccion = seccion
    fiscal.save()
    fiscal.refresh_from_db()
    distrito_preset = f'<input id="id_distrito" name="distrito" type="hidden" tabindex="-1" value="{seccion.distrito.id}" />'
    seccion_preset =  f'<input id="id_seccion" name="seccion" type="hidden" tabindex="-1" value="{seccion.id}" />'

    response = fiscal_client.get(reverse('agregar-adjuntos'))
    content = response.content.decode('utf8')

    assert distrito_preset in content
    assert seccion_preset in content
