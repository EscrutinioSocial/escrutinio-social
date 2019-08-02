from fiscales.tests.test_view_fiscales import construir_request_data
from fiscales.forms import QuieroSerFiscalForm, votomesareportadoformset_factory

from elecciones.tests.factories import (
    FiscalFactory,
    MesaFactory,
    OpcionFactory,
    SeccionFactory,
)
from .test_carga_datos import _construir_request_data_para_carga_de_resultados


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

    FiscalFactory(dni=request_data['dni'])

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


def test_formset_carga_valida_votos_para_opcion(db):
    m = MesaFactory()
    o1, o2 = OpcionFactory(), OpcionFactory()
    votos_para_opcion = {o1.id: 10}

    VMRFormSet = votomesareportadoformset_factory(min_num=2)
    data = _construir_request_data_para_carga_de_resultados(
        [(o1.id, 10, False), (o2.id, 5, False)]
    )
    formset = VMRFormSet(data=data, mesa=m, datos_previos=votos_para_opcion)
    assert formset.is_valid()
    data = _construir_request_data_para_carga_de_resultados(
        [(o1.id, 5, False), (o2.id, 5, False)]
    )
    formset = VMRFormSet(data=data, mesa=m, datos_previos=votos_para_opcion)
    assert not formset.is_valid()

    # error en el campo votos  del primer form, correspondiente a o1.
    assert formset.errors[0]['votos'][0] == 'El valor confirmado que tenemos para esta opción es 10'
