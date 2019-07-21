from elecciones.models import Carga
from elecciones.tests.factories import (
    UserFactory, FiscalFactory, IdentificacionFactory,
    OpcionFactory, CategoriaFactory, CargaFactory, VotoMesaReportadoFactory
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


def nueva_categoria(nombres_opciones):
    opciones = list(map(lambda n: OpcionFactory(nombre=n), nombres_opciones))
    return CategoriaFactory(opciones=opciones)


def nueva_carga(mesa_categoria, fiscal, votos_opciones):
  carga = CargaFactory(mesa_categoria=mesa_categoria, fiscal=fiscal, tipo=Carga.TIPOS.total)
  for opcionConVotos in zip(mesa_categoria.categoria.opciones.order_by('nombre'), votos_opciones):
    VotoMesaReportadoFactory(carga=carga, opcion=opcionConVotos[0], votos=opcionConVotos[1])
  return carga


def reportar_problema_mesa_categoria(mesa_categoria, fiscal):
    return CargaFactory(
        mesa_categoria=mesa_categoria, fiscal=fiscal, tipo=Carga.TIPOS.problema
    )
