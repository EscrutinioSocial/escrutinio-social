from fiscales.tests.test_view_fiscales import construir_request_data
from fiscales.forms import QuieroSerFiscalForm

from elecciones.tests.factories import (
    FiscalFactory,
    SeccionFactory,
)


def test_quiero_ser_fiscal_form__data_ok(db):
    seccion = SeccionFactory()
    request_data = construir_request_data(seccion)
    form = QuieroSerFiscalForm(data=request_data)
    assert form.is_valid()


def test_quiero_ser_fiscal_form__codigo_referido_erroneo(db):
    seccion = SeccionFactory()
    request_data = construir_request_data(seccion)
    request_data["referido_por_codigo"] = "1233245"

    form = QuieroSerFiscalForm(data=request_data)
    assert not form.is_valid()
    assert form.errors['referido_por_codigo'][0] == QuieroSerFiscalForm.MENSAJE_ERROR_CODIGO_REF


def test_quiero_ser_fiscal_form__telefono_no_correcto_formato_nacional(db):
    seccion = SeccionFactory()
    request_data = construir_request_data(seccion)
    request_data["telefono_local"] = "1233245"
    request_data["telefono_area"] = "1234"

    form = QuieroSerFiscalForm(data=request_data)
    assert not form.is_valid()
    error_formato_nacional = "Revisá el código de área y teléfono.Entre ambos deben ser 10 números"
    assert form.errors['telefono_local'][0] == error_formato_nacional
    assert form.errors['telefono_local'][1] == QuieroSerFiscalForm.MENSAJE_ERROR_TELEFONO_INVALIDO
    assert form.errors['telefono_area'][0] == error_formato_nacional
    assert form.errors['telefono_area'][1] == QuieroSerFiscalForm.MENSAJE_ERROR_TELEFONO_INVALIDO


def test_quiero_ser_fiscal_form__dni_repetido(db):
    seccion = SeccionFactory()
    request_data = construir_request_data(seccion)

    FiscalFactory(dni=request_data['dni'], referido_codigo="1234")

    form = QuieroSerFiscalForm(data=request_data)
    assert not form.is_valid()

    assert form.errors['dni'][0] == QuieroSerFiscalForm.MENSAJE_ERROR_DNI_REPETIDO


def test_quiero_ser_fiscal_form__password_no_iguales(db):
    seccion = SeccionFactory()
    request_data = construir_request_data(seccion)
    request_data["password_confirmacion"] = "cualquier_otro_password"
    form = QuieroSerFiscalForm(data=request_data)
    assert not form.is_valid()

    assert form.errors['password_confirmacion'][0] == QuieroSerFiscalForm.MENSAJE_ERROR_PASSWORD_NO_IGUALES


def test_quiero_ser_fiscal_form__limpieza_de_ceros_telefono_area(db):
    seccion = SeccionFactory()
    request_data = construir_request_data(seccion)
    request_data["telefono_area"] = "011"
    form = QuieroSerFiscalForm(data=request_data)
    assert form.is_valid()
    assert form.cleaned_data.get("telefono_area") == "11"
