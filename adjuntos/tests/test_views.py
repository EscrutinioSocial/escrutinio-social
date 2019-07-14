from elecciones.tests.factories import (
    AttachmentFactory,
    MesaFactory,
)
from adjuntos.models import Attachment
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from elecciones.tests.test_resultados import fiscal_client  # noqa
from adjuntos.views import MENSAJE_NINGUN_ATTACHMENT_VALIDO, MENSAJE_SOLO_UN_ACTA
import os 
from http import HTTPStatus

def test_identificacion_create_view_get(fiscal_client):
    a = AttachmentFactory()
    response = fiscal_client.get(reverse('asignar-mesa', args=[a.id]))
    assert response.status_code == HTTPStatus.OK
    assert a.foto.url in a.foto.url in response.content.decode('utf8')

def test_identificacion_create_view_get__desde_unidad_basica(fiscal_client):
    a = AttachmentFactory()
    response = fiscal_client.get(reverse('asignar-mesa-ub', args=[a.id]))
    assert response.status_code == HTTPStatus.OK
    assert a.foto.url in a.foto.url in response.content.decode('utf8')

def test_identificacion_create_view_post__desde_unidad_basica(fiscal_client):
    m1 = MesaFactory()
    a = AttachmentFactory()
    data = {
        'mesa': m1.id,
        'circuito': m1.circuito.id,
        'seccion': m1.circuito.seccion.id,
        'distrito': m1.circuito.seccion.distrito.id,
    }
    response = fiscal_client.post(reverse('asignar-mesa-ub', args=[a.id]), data)
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('procesar-acta-mesa', kwargs={'mesa_id': m1.id})
    assert a.identificaciones.count() == 1
    i = a.identificaciones.first()
    assert i.status == 'identificada'
    assert i.mesa == m1
    assert not i.consolidada
    # la identificacion todavia no está consolidada
    assert not m1.attachments.exists()


def test_identificacion_create_view_post(fiscal_client, admin_user):
    m1 = MesaFactory()
    a = AttachmentFactory()
    data = {
        'mesa': m1.id,
        'circuito': m1.circuito.id,
        'seccion': m1.circuito.seccion.id,
        'distrito': m1.circuito.seccion.distrito.id,
    }
    response = fiscal_client.post(reverse('asignar-mesa', args=[a.id]), data)
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("elegir-adjunto")
    assert a.identificaciones.count() == 1
    i = a.identificaciones.first()
    assert i.status == 'identificada'
    assert i.mesa == m1
    assert i.fiscal == admin_user.fiscal
    assert not i.consolidada
    # la identificacion todavia no está consolidada
    assert not m1.attachments.exists()


def test_identificacion_problema_create_view_post(fiscal_client, admin_user):
    m1 = MesaFactory()
    a = AttachmentFactory()
    data = {
        'status': 'spam',
    }
    response = fiscal_client.post(reverse('asignar-problema', args=[a.id]), data)
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("elegir-adjunto")
    assert a.identificaciones.count() == 1
    i = a.identificaciones.first()
    assert i.status == 'spam'
    assert i.fiscal == admin_user.fiscal
    assert i.mesa is None
    assert not i.consolidada
    # mesa no tiene attach aun
    assert not m1.attachments.exists()


def test_subir_adjunto_unidad_basica__sin_adjuntos(fiscal_client):
    data = {}
    response = fiscal_client.post(reverse('agregar-adjuntos-ub'))

    assert response.status_code == HTTPStatus.OK
    form_errors = response.context['form'].errors 
    
    assert len(form_errors) == 1
    assert len(form_errors['file_field']) == 1
    assert form_errors['file_field'][0] == "This field is required."

def test_subir_adjunto_unidad_basica__no_imagen(fiscal_client):
    este_directorio = os.path.dirname(os.path.realpath(__file__))
    no_imagen = open(os.path.join(este_directorio, 'archivo_no_imagen.txt'),'rb') 
    data = { 'file_field' : no_imagen}
    response = fiscal_client.post(reverse('agregar-adjuntos-ub'), data)

    assert response.status_code == HTTPStatus.OK
    form_errors = response.context['form'].errors 
    
    assert len(form_errors) == 1
    assert len(form_errors['file_field']) == 1
    assert form_errors['file_field'][0] == MENSAJE_NINGUN_ATTACHMENT_VALIDO

def test_subir_adjunto_unidad_basica__varias_imagenes(fiscal_client):
    simple_upload_1 = _get_adjunto_para_subir('acta.jpg')
    simple_upload_2 = _get_adjunto_para_subir('acta2.jpg')
    

    data = { 'file_field' : [simple_upload_1,simple_upload_2]}
    response = fiscal_client.post(reverse('agregar-adjuntos-ub'), data)

    assert response.status_code == HTTPStatus.OK
    form_errors = response.context['form'].errors 
    
    assert len(form_errors) == 1
    assert len(form_errors['file_field']) == 1
    assert form_errors['file_field'][0] == MENSAJE_SOLO_UN_ACTA

def test_subir_adjunto_unidad_basica__imagen_valida(fiscal_client):
    #primero chequeamos que no haya ninguna acta sin identificar
    assert len(set(Attachment.sin_identificar())) == 0

    simple_upload_1 = _get_adjunto_para_subir('acta.jpg')
    data = { 'file_field' : simple_upload_1}
    #subimos el acta
    response = fiscal_client.post(reverse('agregar-adjuntos-ub'), data)

    assert response.status_code == HTTPStatus.FOUND
    
    conjunto_actas_sin_identificar = set(Attachment.sin_identificar())

    #chequeamos que haya una
    assert len(conjunto_actas_sin_identificar) == 1
    
    acta_sin_identificar = conjunto_actas_sin_identificar.pop()
    #y chequeamos que nos mande a asignar mesa
    assert response.url == reverse('asignar-mesa-ub', args=[acta_sin_identificar.id])



def _get_adjunto_para_subir(nombre_archivo, content_type='image/jpeg'):
    este_directorio = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(este_directorio, nombre_archivo),'rb') as infile:
        return SimpleUploadedFile(nombre_archivo, infile.read(), content_type)