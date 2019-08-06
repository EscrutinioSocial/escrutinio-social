import html

from django.urls import reverse

from adjuntos.models import Identificacion
from adjuntos.consolidacion import consumir_novedades_identificacion
from elecciones.models import (
    MesaCategoria,
    Carga,
    Opcion
)
from elecciones.resultados import Sumarizador
from elecciones.tests.factories import (
    CargaFactory,
    CategoriaFactory,
    IdentificacionFactory,
    MesaFactory,
    VotoMesaReportadoFactory,
)
from elecciones.tests.test_resultados import (
    fiscal_client,
    setup_groups,
    carta_marina
)
from .test_models import consumir_novedades_y_actualizar_objetos


def test_resultados__generacion_url_ver_mesas_circuito(fiscal_client):
    categoria = CategoriaFactory(nombre='default')
    mesa1 = IdentificacionFactory(status='identificada', source=Identificacion.SOURCES.csv).mesa
    consumir_novedades_identificacion()

    url = reverse('resultados-categoria', args=[categoria.id])

    response = fiscal_client.get(url)
    
    assert response.status_code == 200

    texto_mesas_link = "Ver mesas del circuito"

    assert texto_mesas_link not in response.content.decode('utf8')
    
    response = fiscal_client.get(url, {"circuito": mesa1.circuito.id})
    
    # como ahora en la URL hay especificado un circuito, debería aparecer el link de "Ver las mesas..."
    assert response.status_code == 200
    assert texto_mesas_link in response.content.decode('utf8')
    url_mesa_distrito = reverse('mesas-circuito', args=[categoria.id])
    assert url_mesa_distrito in response.content.decode('utf8')


def test_mesa_de_circuito__dispatch_primera_mesa_numero(carta_marina, fiscal_client):
    mesa1, mesa2, *otras_mesas = carta_marina
    categoria = mesa1.categorias.get()
    query_string_circuito = (
        f'?circuito={mesa1.circuito.id}'
        '&tipoDeAgregacion=todas_las_cargas&opcionaConsiderar=todas'
        )
    url_circuito = reverse('mesas-circuito', args=[categoria.id]) + query_string_circuito
    response = fiscal_client.get(url_circuito)

    assert response.status_code == 302
    assert url_circuito in response.url
    assert f"mesa={mesa1.id}" in response.url


def test_mesa_de_circuito__sidebar_mesas(carta_marina, fiscal_client):
    # el sidebar debería tener dos links a cada mesa si entro con el id del circuito
    mesa1, mesa2, *otras_mesas = carta_marina
    categoria = mesa1.categorias.get()

    query_string_circuito = (
        f'?circuito={mesa1.circuito.id}&mesa={mesa1.id}'
        '&tipoDeAgregacion=todas_las_cargas&opcionaConsiderar=todas'
        )
    url_circuito = reverse('mesas-circuito', args=[categoria.id]) + query_string_circuito
    response = fiscal_client.get(url_circuito)

    assert response.status_code == 200

    content = response.content.decode('utf8')
    # sabemos que no hay resultados para las mesas, pero los links deben estar en el costado
    assert response.context['mensaje_no_hay_info'] in content

    assert f'<li id="mesa-{mesa1.id}" class="active">' in content
    assert f'<li id="mesa-{mesa2.id}" >' in content


def test_mesa_de_circuito__navegacion_categorías(fiscal_client):
    categoria1 = CategoriaFactory(nombre='cat1')
    categoria2 = CategoriaFactory(nombre='cat2')

    mesa1 = MesaFactory(categorias=[categoria1, categoria2])

    query_string_mesa_1 = (
        f'?mesa={mesa1.id}&circuito={mesa1.circuito.id}'
        '&tipoDeAgregacion=todas_las_cargas&opcionaConsiderar=todas'
        )

    url_mesa_1 = reverse('mesas-circuito', args=[categoria1.id]) + query_string_mesa_1
    response = fiscal_client.get(url_mesa_1)

    assert response.status_code == 200
    content = html.unescape(response.content.decode('utf-8'))
    assert response.context['mensaje_no_hay_info'] in content

    link_categoria_1 = f"   href=\"/elecciones/mesas_circuito/{categoria1.id}{query_string_mesa_1}\""
    link_categoria_2 = f"   href=\"/elecciones/mesas_circuito/{categoria2.id}{query_string_mesa_1}\""

    assert link_categoria_1 in content
    assert link_categoria_2 in content


def test_mesa_de_circuito__url_mesa_sin_resultados(fiscal_client):
    categoria = CategoriaFactory(nombre='default')
    mesa1 = IdentificacionFactory(status='identificada', source=Identificacion.SOURCES.csv).mesa
    consumir_novedades_identificacion()
    query_string_mesa_1 = (
        f'?mesa={mesa1.id}&circuito={mesa1.circuito.id}'
        '&tipoDeAgregacion=todas_las_cargas&opcionaConsiderar=todas'
        )
    url_mesa_1 = reverse('mesas-circuito', args=[categoria.id]) + query_string_mesa_1
    response = fiscal_client.get(url_mesa_1)

    assert response.status_code == 200
    assert response.context['mensaje_no_hay_info'] in response.content.decode('utf-8')
    assert not response.context['resultados'].exists()


def test_mesa_de_circuito__url_mesa_con_resultados(carta_marina, fiscal_client):
    # resultados para mesa 1
    mesa1, *otras_mesas = carta_marina
    categoria = mesa1.categorias.get()  # sólo default
    # opciones a partido
    o1, o2, o3, o4 = categoria.opciones.filter(partido__isnull=False)
    # la opción 4 pasa a ser del mismo partido que la 1
    o4.partido = o1.partido
    o4.save()

    blanco = Opcion.blancos()
    total = Opcion.total_votos()

    mc1 = MesaCategoria.objects.get(mesa=mesa1, categoria=categoria)
    carga = CargaFactory(mesa_categoria=mc1, tipo=Carga.TIPOS.parcial)

    consumir_novedades_y_actualizar_objetos([mesa1])

    VotoMesaReportadoFactory(carga=carga, opcion=o1, votos=20)
    VotoMesaReportadoFactory(carga=carga, opcion=o2, votos=30)
    VotoMesaReportadoFactory(carga=carga, opcion=o3, votos=40)
    VotoMesaReportadoFactory(carga=carga, opcion=o4, votos=5)

    # votaron 95/100 personas
    VotoMesaReportadoFactory(carga=carga, opcion=blanco, votos=5)
    VotoMesaReportadoFactory(carga=carga, opcion=total, votos=100)

    carga.actualizar_firma()

    assert carga.es_testigo.exists()

    query_string_mesa_1 = (
        f'?mesa={mesa1.id}&circuito={mesa1.circuito.id}'
        '&tipoDeAgregacion=todas_las_cargas'
        f'&opcionaConsiderar={Sumarizador.OPCIONES_A_CONSIDERAR.prioritarias}'
        )
    url_mesa_1 = reverse('mesas-circuito', args=[categoria.id]) + query_string_mesa_1
    response = fiscal_client.get(url_mesa_1)

    assert response.status_code == 200

    content = response.content.decode('utf8')
    assert response.context['mensaje_no_hay_info'] not in content

    resultados = response.context['resultados']
    assert len(resultados) == 6  # 4 opciones + blanco + total

    for voto_mesa_reportado in resultados:
        assert f'<th>{voto_mesa_reportado.opcion}</th>' in content
        assert f'<td>{voto_mesa_reportado.votos}</td>' in content
