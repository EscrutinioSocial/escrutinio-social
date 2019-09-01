import pytest

from http import HTTPStatus

from django.urls import reverse
from elecciones.tests.factories import (
    AttachmentFactory,
    CargaFactory,
    CategoriaFactory,
    CategoriaOpcionFactory,
    IdentificacionFactory,
    MesaCategoriaFactory,
    MesaFactory,
    OpcionFactory,
    VotoMesaReportadoFactory,
    FiscalFactory
)
from constance.test import override_config

from elecciones.tests.conftest import fiscal_client, setup_groups, fiscal_client_from_fiscal    # noqa
from elecciones.models import Carga, MesaCategoria, Opcion
from adjuntos.models import Identificacion
from adjuntos.consolidacion import consumir_novedades_identificacion, consumir_novedades_carga

from elecciones.tests.test_models import consumir_novedades_y_actualizar_objetos


def test_siguiente_accion_sin_mesas(fiscal_client):
    response = fiscal_client.get(reverse('siguiente-accion'))
    assert 'No hay actas para cargar por el momento' in response.content.decode('utf8')


@pytest.mark.parametrize('cant_attachments, cant_mcs, coeficiente, expect', [
    [1, 0, 2.0, 'asignar-mesa'],   # solo hay para identificar
    [0, 1, 2.0, 'carga-total'],    # solo hay para cargar
    [1, 1, 2.0, 'carga-total'],
    [1, 2, 2.0, 'carga-total'],
    [1, 3, 2.0, 'carga-total'],
    [2, 1, 2.0, 'asignar-mesa'],   # muchas actas acumuladas
    [3, 1, 2.0, 'asignar-mesa'],
    [4, 2, 2.0, 'asignar-mesa'],

    # ahora con otros coeficientes
    [2, 1, 3.0, 'carga-total'],   # hacen falta 3
    [3, 1, 3.0, 'asignar-mesa'],
    [1, 1, 0.5, 'asignar-mesa'],

])
def test_siguiente_accion_balancea(fiscal_client, cant_attachments, cant_mcs, coeficiente, expect):
    attachments = AttachmentFactory.create_batch(cant_attachments, status='sin_identificar')
    mesas = MesaFactory.create_batch(cant_mcs)
    for i in range(cant_mcs):
        attachment_identificado = AttachmentFactory(mesa=mesas[i], status='identificada')
        MesaCategoriaFactory(mesa=mesas[i], orden_de_carga=1)

    # Como la URL de identificación pasa un id no predictible
    # y no nos importa acá saber exactamente a que instancia se relaciona la acción
    # lo que evalúo es que redirija a una url que empiece así.
    beginning = reverse(expect, args=[0])[:10]

    with override_config(COEFICIENTE_IDENTIFICACION_VS_CARGA=coeficiente):
        response = fiscal_client.get(reverse('siguiente-accion'))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(beginning)


def test_siguiente_accion_redirige_a_cargar_resultados(db, settings, client, setup_groups):
    c1 = CategoriaFactory()
    c2 = CategoriaFactory()
    m1 = MesaFactory(categorias=[c1])
    IdentificacionFactory(
        mesa=m1,
        status='identificada',
        source=Identificacion.SOURCES.csv,
    )
    m2 = MesaFactory(categorias=[c1, c2])
    assert MesaCategoria.objects.count() == 3
    IdentificacionFactory(
        mesa=m2,
        status='identificada',
        source=Identificacion.SOURCES.csv,
    )
    # Ambas consolidadas vía csv.
    consumir_novedades_identificacion()

    # Los fiscales que voy a usar.
    fiscales = FiscalFactory.create_batch(20)
    indice_fiscal = 0

    m1c1 = MesaCategoria.objects.get(mesa=m1, categoria=c1)
    for i in range(settings.MIN_COINCIDENCIAS_CARGAS):
        fiscal_client = fiscal_client_from_fiscal(client, fiscales[indice_fiscal])
        indice_fiscal += 1
        response = fiscal_client.get(reverse('siguiente-accion'))
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse('carga-total', args=[m1c1.id])
        # Cerramos la sesión para que el client pueda reutilizarse sin que nos diga
        # que ya estamos logueados.
        fiscal_client.logout()

    # Como m1c1 ya fue pedida por suficientes fiscales,
    # se pasa a la siguiente mesacategoría.
    m2c1 = MesaCategoria.objects.get(mesa=m2, categoria=c1)
    for i in range(settings.MIN_COINCIDENCIAS_CARGAS):
        fiscal_client = fiscal_client_from_fiscal(client, fiscales[indice_fiscal])
        indice_fiscal += 1
        response = fiscal_client.get(reverse('siguiente-accion'))
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse('carga-total', args=[m2c1.id])
        fiscal_client.logout()

    # Ahora la tercera.
    m2c2 = MesaCategoria.objects.get(mesa=m2, categoria=c2)
    for i in range(settings.MIN_COINCIDENCIAS_CARGAS):
        fiscal_client = fiscal_client_from_fiscal(client, fiscales[indice_fiscal])
        indice_fiscal += 1
        response = fiscal_client.get(reverse('siguiente-accion'))
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse('carga-total', args=[m2c2.id])
        fiscal_client.logout()

    # Ya no hay actas nuevas, vuelta a empezar.
    fiscal_client = fiscal_client_from_fiscal(client, fiscales[indice_fiscal])
    indice_fiscal += 1
    response = fiscal_client.get(reverse('siguiente-accion'))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('carga-total', args=[m1c1.id])
    fiscal_client.logout()

    # Se libera una.
    m2c2.desasignar_a_fiscal()
    fiscal_client = fiscal_client_from_fiscal(client, fiscales[indice_fiscal])
    indice_fiscal += 1
    response = fiscal_client.get(reverse('siguiente-accion'))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('carga-total', args=[m2c2.id])


def test_siguiente_accion_considera_cant_asignaciones_realizadas(db, fiscal_client, settings):
    c1 = CategoriaFactory()
    c2 = CategoriaFactory()
    m1 = MesaFactory(categorias=[c1])
    IdentificacionFactory(
        mesa=m1,
        status='identificada',
        source=Identificacion.SOURCES.csv,
    )
    m2 = MesaFactory(categorias=[c1, c2])
    assert MesaCategoria.objects.count() == 3
    IdentificacionFactory(
        mesa=m2,
        status='identificada',
        source=Identificacion.SOURCES.csv,
    )
    # Ambas consolidadas vía csv.
    consumir_novedades_identificacion()

    m1c1 = MesaCategoria.objects.get(mesa=m1, categoria=c1)
    for i in range(settings.MIN_COINCIDENCIAS_CARGAS * 2):
        response = fiscal_client.get(reverse('siguiente-accion'))
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse('carga-total', args=[m1c1.id])
        # Fiscal devuelve.
        m1c1.desasignar_a_fiscal()

    # Como m1c1 ya fue pedida por suficientes fiscales,
    # se pasa a la siguiente mesacategoría por más que m1c1 esté en
    # cero fiscales asignados. Ie, no da siempre la misma tarea.
    m1c1.refresh_from_db()
    assert m1c1.cant_fiscales_asignados == 0
    assert m1c1.cant_asignaciones_realizadas == settings.MIN_COINCIDENCIAS_CARGAS * 2
    m2c1 = MesaCategoria.objects.get(mesa=m2, categoria=c1)
    assert m2c1.cant_fiscales_asignados == 0
    assert m2c1.cant_asignaciones_realizadas == 0
    for i in range(settings.MIN_COINCIDENCIAS_CARGAS * 2):
        response = fiscal_client.get(reverse('siguiente-accion'))
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse('carga-total', args=[m2c1.id])
        # Fiscal devuelve.
        m2c1.desasignar_a_fiscal()

    m2c1.refresh_from_db()
    assert m2c1.cant_fiscales_asignados == 0
    assert m2c1.cant_asignaciones_realizadas == settings.MIN_COINCIDENCIAS_CARGAS * 2

    # Ahora la tercera
    m2c2 = MesaCategoria.objects.get(mesa=m2, categoria=c2)
    for i in range(settings.MIN_COINCIDENCIAS_CARGAS * 2):
        response = fiscal_client.get(reverse('siguiente-accion'))
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse('carga-total', args=[m2c2.id])
        # Fiscal devuelve.
        m2c2.desasignar_a_fiscal()

    m2c2.refresh_from_db()
    assert m2c2.cant_fiscales_asignados == 0
    assert m2c2.cant_asignaciones_realizadas == settings.MIN_COINCIDENCIAS_CARGAS * 2

    # Ya no hay actas nuevas, vuelta a empezar.
    response = fiscal_client.get(reverse('siguiente-accion'))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('carga-total', args=[m1c1.id])

@pytest.mark.parametrize('status, parcial', [
    (MesaCategoria.STATUS.sin_cargar, True),
    (MesaCategoria.STATUS.parcial_sin_consolidar, True),
    (MesaCategoria.STATUS.parcial_en_conflicto, True),
    (MesaCategoria.STATUS.parcial_consolidada_csv, True),
    (MesaCategoria.STATUS.parcial_consolidada_dc, False),
    (MesaCategoria.STATUS.total_sin_consolidar, False),
    (MesaCategoria.STATUS.total_en_conflicto, False),
    (MesaCategoria.STATUS.total_consolidada_csv, False),
])
def test_cargar_resultados_redirige_a_parcial_si_es_necesario(db, fiscal_client, status, parcial):
    mesa = MesaFactory()
    a = AttachmentFactory(mesa=mesa)
    c1 = CategoriaFactory(requiere_cargas_parciales=True)
    m1c1 = MesaCategoriaFactory(categoria=c1, orden_de_carga=0.1, status=status, mesa=mesa)
    response = fiscal_client.get(reverse('siguiente-accion'))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('carga-parcial' if parcial else 'carga-total', args=[m1c1.id])


def test_siguiente_happy_path_parcial_y_total(db, fiscal_client, settings):
    settings.MIN_COINCIDENCIAS_CARGAS = 1
    mesa = MesaFactory()
    a = AttachmentFactory(mesa=mesa, status='identificada')
    mc1 = MesaCategoriaFactory(categoria__requiere_cargas_parciales=True, orden_de_carga=1,
        mesa=mesa
    )
    response = fiscal_client.get(reverse('siguiente-accion'))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('carga-parcial', args=[mc1.id])

    carga = CargaFactory(mesa_categoria=mc1, tipo='parcial')
    consumir_novedades_carga()
    mc1.refresh_from_db()
    assert mc1.status == MesaCategoria.STATUS.parcial_consolidada_dc
    assert mc1.carga_testigo == carga
    mc1.desasignar_a_fiscal()
    response = fiscal_client.get(reverse('siguiente-accion'))
    assert response.url == reverse('carga-total', args=[mc1.id])

    carga = CargaFactory(mesa_categoria=mc1, tipo='total')
    consumir_novedades_carga()
    mc1.refresh_from_db()
    assert mc1.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mc1.carga_testigo == carga
    response = fiscal_client.get(reverse('siguiente-accion'))
    # No hay actas para cargar, vuelta a empezar.
    assert response.status_code == HTTPStatus.OK


def test_siguiente_manda_a_parcial_si_es_requerido(db, fiscal_client, settings):
    settings.MIN_COINCIDENCIAS_CARGAS = 1
    m1 = MesaFactory()
    a1 = AttachmentFactory(mesa=m1, status='identificada')
    m2 = MesaFactory()
    a2 = AttachmentFactory(mesa=m2, status='identificada')
    mc1 = MesaCategoriaFactory(categoria__requiere_cargas_parciales=False, orden_de_carga=1,
        mesa=m1
    )
    mc2 = MesaCategoriaFactory(categoria__requiere_cargas_parciales=True, orden_de_carga=2,
        mesa=m2
    )

    response = fiscal_client.get(reverse('siguiente-accion'))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('carga-total', args=[mc1.id])

    # mc1 fue asignada, ahora da mc2

    response = fiscal_client.get(reverse('siguiente-accion'))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('carga-parcial', args=[mc2.id])


def test_formset_en_carga_parcial_solo_muestra_prioritarias(db, fiscal_client, admin_user):
    c = CategoriaFactory()
    o = CategoriaOpcionFactory(categoria=c, prioritaria=True).opcion

    # La opción 2 no se muestra
    CategoriaOpcionFactory(categoria=c, prioritaria=False).opcion
    mc = MesaCategoriaFactory(categoria=c)
    mc.asignar_a_fiscal()
    admin_user.fiscal.asignar_mesa_categoria(mc)  # Para que no lo mande a otra por falta de permisos.

    parciales = reverse('carga-parcial', args=[mc.id])
    response = fiscal_client.get(parciales)

    # Sólo hay un formulario (e de o)
    assert len(response.context['formset']) == 1
    assert response.context['formset'][0].fields['opcion'].choices == [(o.id, o)]


def test_formset_en_carga_total_muestra_todos(db, fiscal_client, admin_user):
    c = CategoriaFactory(id=100, opciones=[])
    o = CategoriaOpcionFactory(categoria=c, opcion__orden=3, prioritaria=True).opcion
    o2 = CategoriaOpcionFactory(categoria=c, opcion__orden=1, prioritaria=False).opcion
    mc = MesaCategoriaFactory(categoria=c)
    mc.asignar_a_fiscal()
    admin_user.fiscal.asignar_mesa_categoria(mc)  # Para que no lo mande a otra por falta de permisos.
    totales = reverse('carga-total', args=[mc.id])
    response = fiscal_client.get(totales)
    assert len(response.context['formset']) == 2 + len(Opcion.opciones_no_partidarias())
    assert response.context['formset'][0].fields['opcion'].choices == [(o2.id, o2)]
    assert response.context['formset'][1].fields['opcion'].choices == [(o.id, o)]


def test_formset_en_carga_total_reusa_parcial_confirmada(db, fiscal_client, admin_user, settings):
    # Solo una carga, para simplificar el setup
    settings.MIN_COINCIDENCIAS_CARGAS = 1

    c = CategoriaFactory(id=25000, opciones=[])
    # Notar que el orden no coincide con el id

    o1 = CategoriaOpcionFactory(categoria=c, opcion__orden=3, prioritaria=True).opcion
    o2 = CategoriaOpcionFactory(categoria=c, opcion__orden=1, prioritaria=False).opcion
    o3 = CategoriaOpcionFactory(categoria=c, opcion__orden=2, prioritaria=False).opcion
    o4 = CategoriaOpcionFactory(categoria=c, opcion__orden=4, prioritaria=True).opcion

    mc = MesaCategoriaFactory(categoria=c)
    mc.asignar_a_fiscal()
    admin_user.fiscal.asignar_mesa_categoria(mc)

    # Se carga parcialente, la opcion prioritaira "o"
    carga = CargaFactory(mesa_categoria=mc, tipo='parcial')
    VotoMesaReportadoFactory(carga=carga, opcion=o1, votos=10)
    VotoMesaReportadoFactory(carga=carga, opcion=o4, votos=3)

    # Consolidamos.
    consumir_novedades_carga()
    mc.refresh_from_db()
    assert mc.status == MesaCategoria.STATUS.parcial_consolidada_dc
    assert mc.carga_testigo == carga
    assert set(carga.opcion_votos()) == {(o1.id, 10), (o4.id, 3)}

    # Ahora pedimos la carga total
    totales = reverse('carga-total', args=[mc.id])
    response = fiscal_client.get(totales)

    # Tenemos las tres opciones en orden
    assert len(response.context['formset']) == 4 + len(Opcion.opciones_no_partidarias())
    assert response.context['formset'][0].initial['opcion'] == o2
    assert response.context['formset'][1].initial['opcion'] == o3
    assert response.context['formset'][2].initial['opcion'] == o1
    assert response.context['formset'][3].initial['opcion'] == o4

    # y los valores de los votos
    assert response.context['formset'][0].initial['votos'] is None
    assert response.context['formset'][1].initial['votos'] is None
    assert response.context['formset'][2].initial['votos'] == 10
    assert response.context['formset'][3].initial['votos'] == 3

    # el valor previo es readonly
    assert response.context['formset'][2].fields['votos'].widget.attrs['readonly'] is True
    assert response.context['formset'][3].fields['votos'].widget.attrs['readonly'] is True


def test_formset_reusa_metadata(db, fiscal_client, admin_user):
    # hay una categoria con una opcion metadata ya consolidada
    o1 = OpcionFactory(tipo=Opcion.TIPOS.metadata, orden=1)
    cat1 = CategoriaFactory(opciones=[o1])
    mc = MesaCategoriaFactory(categoria=cat1, status=MesaCategoria.STATUS.total_consolidada_dc)
    carga = CargaFactory(mesa_categoria=mc, tipo='total')
    VotoMesaReportadoFactory(carga=carga, opcion=o1, votos=10)

    # otra categoria incluye la misma metadata.
    o2 = OpcionFactory(orden=2)
    cat2 = CategoriaFactory(opciones=[o1, o2])
    mc2 = MesaCategoriaFactory(categoria=cat2, mesa=mc.mesa)

    mc2.asignar_a_fiscal()
    admin_user.fiscal.asignar_mesa_categoria(mc2)
    response = fiscal_client.get(reverse('carga-total', args=[mc2.id]))
    assert len(response.context['formset']) == 2 + len(Opcion.opciones_no_partidarias())
    assert response.context['formset'][0].initial['opcion'] == o1
    assert response.context['formset'][1].initial['opcion'] == o2

    # y los valores de los votos
    assert response.context['formset'][0].initial['votos'] == 10
    assert response.context['formset'][0].fields['votos'].widget.attrs['readonly'] is True

    assert response.context['formset'][1].initial['votos'] is None


def test_carga_envia_datos_previos_al_formset(db, fiscal_client, admin_user, mocker):
    sentinela = mocker.MagicMock()
    mocker.patch('elecciones.models.MesaCategoria.datos_previos', return_value=sentinela)
    mc = MesaCategoriaFactory()
    mc.asignar_a_fiscal()
    admin_user.fiscal.asignar_mesa_categoria(mc)
    response = fiscal_client.get(reverse('carga-total', args=[mc.id]))
    assert response.context['formset'].datos_previos is sentinela


def test_detalle_mesa_categoria(db, fiscal_client):
    opcs = OpcionFactory.create_batch(3)
    e1 = CategoriaFactory(opciones=opcs)
    e2 = CategoriaFactory(opciones=opcs)
    mesa = MesaFactory(categorias=[e1, e2])
    c1 = CargaFactory(
        mesa_categoria__mesa=mesa,
        mesa_categoria__categoria=e1,
        tipo=Carga.TIPOS.parcial,
        origen=Carga.SOURCES.csv
    )
    mc = c1.mesa_categoria
    votos1 = VotoMesaReportadoFactory(
        opcion=opcs[0],
        votos=1,
        carga=c1,
    )
    votos2 = VotoMesaReportadoFactory(
        opcion=opcs[1],
        votos=2,
        carga=c1,
    )
    votos3 = VotoMesaReportadoFactory(
        opcion=opcs[2],
        votos=1,
        carga=c1,
    )

    # a otra carga
    VotoMesaReportadoFactory(
        opcion=opcs[2],
        votos=1
    )
    c1.actualizar_firma()
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.carga_testigo == c1
    url = reverse('detalle-mesa-categoria', args=[e1.id, mesa.numero])
    response = fiscal_client.get(url)

    assert list(response.context['reportados']) == [votos1, votos2, votos3]


def test_cargar_resultados_mesa_desde_ub_con_id_de_mesa(
    db, fiscal_client, admin_user, django_assert_num_queries
):
    """
    Es un test desaconsejadamente largo, pero me sirvió para entender el escenario.
    Se hace un recorrido por la carga de dos categorías desde una UB.

    Cuando se llama a procesar-acta-mesa, cuando va por GET, es para cargar el template carga-ub.html.
    Cuando se le pega con POST, va a cargar un resultado.

    Cuando ya no tiene más categorías para cargar, te devuelve a agregar-adjunto-ub
    """
    categoria_1 = CategoriaFactory()
    categoria_2 = CategoriaFactory()

    mesa = MesaFactory(categorias=[categoria_1, categoria_2])

    mesa_categoria_1 = MesaCategoriaFactory(mesa=mesa, categoria=categoria_1, orden_de_carga=1)
    mesa_categoria_2 = MesaCategoriaFactory(mesa=mesa, categoria=categoria_2, orden_de_carga=2)

    opcion_1 = OpcionFactory(orden=1)
    opcion_2 = OpcionFactory(orden=2)

    CategoriaOpcionFactory(categoria=categoria_1, opcion=opcion_1, prioritaria=True)
    CategoriaOpcionFactory(categoria=categoria_1, opcion=opcion_2, prioritaria=True)
    CategoriaOpcionFactory(categoria=categoria_2, opcion=opcion_1, prioritaria=True)
    CategoriaOpcionFactory(categoria=categoria_2, opcion=opcion_2, prioritaria=True)

    AttachmentFactory(mesa=mesa)

    IdentificacionFactory(
        mesa=mesa,
        status=Identificacion.STATUS.identificada,
        source=Identificacion.SOURCES.csv,
    )
    consumir_novedades_identificacion()
    assert MesaCategoria.objects.count() == 2

    for mc in MesaCategoria.objects.all():
        mc.actualizar_orden_de_carga()

    nombre_categoria = "Un nombre en particular" # Sin tilde que si no falla el 'in' más abajo.
    categoria_1.nombre = nombre_categoria
    categoria_1.save(update_fields=['nombre'])

    categoria_2.nombre = 'Otro nombre'
    categoria_2.save(update_fields=['nombre'])

    url_carga = reverse('procesar-acta-mesa', kwargs={'mesa_id': mesa.id})
    response = fiscal_client.get(url_carga)

    # Nos aseguramos que haya cargado el template específico para UB. No es una redirección.
    assert response.status_code == HTTPStatus.OK
    assert url_carga in str(response.content)
    # categoria1 debería aparecer primero porque su mesa categoria tiene un orden_de_carga más grande
    assert nombre_categoria in str(response.content)

    tupla_opciones_electores = [(opcion_1.id, mesa.electores // 2, mesa.electores // 2), (opcion_2.id, mesa.electores // 2, mesa.electores // 2)]
    request_data = _construir_request_data_para_carga_de_resultados(tupla_opciones_electores)
    with django_assert_num_queries(46):
        response = fiscal_client.post(url_carga, request_data)

    # Tiene otra categoría, por lo que debería cargar y redirigirnos nuevamente a procesar-acta-mesa
    carga = Carga.objects.get()
    assert carga.tipo == Carga.TIPOS.total
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('procesar-acta-mesa', kwargs={'mesa_id': mesa.id})

    # Hacemos el get hacia donde nos manda el redirect. Esto hace el take.
    response = fiscal_client.get(response.url)

    # Posteamos los nuevos datos.
    response = fiscal_client.post(url_carga, request_data)

    carga.refresh_from_db()

    cargas = Carga.objects.all()
    assert len(cargas) == 2
    assert carga.tipo == Carga.TIPOS.total

    # Me lleva a continuar con el workflow.
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('procesar-acta-mesa', kwargs={'mesa_id': mesa.id})

    # La mesa no tiene más categorías, nos devuelve a la pantalla de carga de adjuntos.
    
    assert response.status_code == 302
    # Hacemos el get hacia donde nos manda el redirect.
    response = fiscal_client.get(response.url)
    assert response.url == reverse('agregar-adjuntos-ub') 


def test_elegir_acta_mesas_con_id_inexistente_de_mesa_desde_ub(fiscal_client):
    mesa_id_inexistente = 673162312
    url = reverse('procesar-acta-mesa', kwargs={'mesa_id': mesa_id_inexistente})
    response = fiscal_client.get(url)
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_carga_sin_permiso(fiscal_client, admin_user, mocker):
    fiscal = admin_user.fiscal
    capture = mocker.patch('fiscales.views.capture_message')
    mc = MesaCategoriaFactory(orden_de_carga=1)
    response = fiscal_client.get(reverse('carga-total', args=[mc.id]))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('siguiente-accion')  # Manda a asignar una nueva.
    assert capture.call_count == 1
    mensaje = capture.call_args[0][0]
    assert 'Intento de cargar mesa-categoria' in mensaje
    assert str(fiscal) in mensaje
    mc.asignar_a_fiscal()
    fiscal.asignar_mesa_categoria(mc)
    response = fiscal_client.get(reverse('carga-total', args=[mc.id]))
    assert response.status_code == HTTPStatus.OK


def _construir_request_data_para_carga_de_resultados(tuplas_opcion_electores):
    """
    Helper que sirve para ahorrarnos el tema este crear el diccionario para la data del request
    al momento de cargar resultados.

    Se puede hacer más parametrizable.

    Las tuplas opcion_electores tienen que tener (opcion_id, cant_electores)
    """
    request_data = {}
    for index, tupla in enumerate(tuplas_opcion_electores):
        key = f'form-{index}-opcion'
        request_data[key] = str(tupla[0])
        key = f'form-{index}-votos'
        request_data[key] = str(tupla[1])
        key = f'form-{index}-valor-previo'
        request_data[key] = str(tupla[2])
    request_data['form-TOTAL_FORMS'] = str(len(tuplas_opcion_electores))
    request_data['form-INITIAL_FORMS'] = '0'
    request_data['form-MIN_NUM_FORMS'] = str(len(tuplas_opcion_electores))
    request_data['form-MAX_NUM_FORMS'] = '1000'
    return request_data
