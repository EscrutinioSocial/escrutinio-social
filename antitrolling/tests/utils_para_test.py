from elecciones.models import Carga
from elecciones.tests.factories import (
    CargaFactory,
    CategoriaFactory,
    CategoriaOpcionFactory,
    FiscalFactory,
    IdentificacionFactory,
    OpcionFactory,
    UserFactory,
    VotoMesaReportadoFactory,
)


def nuevo_fiscal():
    usuario = UserFactory()
    fiscal = FiscalFactory(user=usuario)
    return fiscal


def identificar(attach, mesa, fiscal):
    return IdentificacionFactory(
        status='identificada',
        attachment=attach,
        mesa=mesa,
        fiscal=fiscal
    )


def reportar_problema_attachment(attach, fiscal):
    return IdentificacionFactory(
        status='problema',
        attachment=attach,
        fiscal=fiscal
    )


def nueva_categoria(nombres_opciones, prioritaria=False):
    categoria = CategoriaFactory(opciones=[])   # sin opciones para crearlas ad hoc
    for nombre in nombres_opciones:
        CategoriaOpcionFactory(categoria=categoria, opcion__nombre=nombre, prioritaria=prioritaria)
    return categoria


def nueva_carga(mesa_categoria, fiscal, votos_opciones, tipo_carga=Carga.TIPOS.total):
    carga = CargaFactory(mesa_categoria=mesa_categoria, fiscal=fiscal, tipo=tipo_carga)
    for opcionVoto, cantidadVotos in zip(mesa_categoria.categoria.opciones.order_by('nombre'), votos_opciones):
        VotoMesaReportadoFactory(carga=carga, opcion=opcionVoto, votos=cantidadVotos)
    return carga


def reportar_problema_mesa_categoria(mesa_categoria, fiscal):
    return CargaFactory(
        mesa_categoria=mesa_categoria, fiscal=fiscal, tipo=Carga.TIPOS.problema
    )
