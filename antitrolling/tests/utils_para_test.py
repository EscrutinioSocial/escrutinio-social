from elecciones.tests.factories import (
    UserFactory, FiscalFactory, IdentificacionFactory
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

