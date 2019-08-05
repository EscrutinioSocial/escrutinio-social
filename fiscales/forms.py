from functools import partial
from django import forms
from django.forms import modelformset_factory, BaseModelFormSet
from material import Layout, Row, Fieldset
from localflavor.ar.forms import ARDNIField
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import ugettext_lazy as _
from django.core.validators import ValidationError, MinLengthValidator, MaxLengthValidator
from django.contrib.auth import password_validation
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.utils.html import format_html

from dal import autocomplete

import phonenumbers

from .models import Fiscal
from elecciones.models import VotoMesaReportado, Categoria, Opcion, Distrito, Seccion


class AuthenticationFormCustomError(AuthenticationForm):
    error_messages = {
        'invalid_login': (
            'Por favor introduzca un nombre de usuario y una contraseña correctos. '
            'Prueba tu DNI o teléfono sin puntos, guiones ni espacios.'
        ),
        'inactive':
        _("This account is inactive."),
    }
    already_logged_message = (
        format_html('Ya hay un usuario sesionado/a con esta cuenta. Si sos vos mismo/a esperá '
        f'{int(settings.SESSION_TIMEOUT / 60)} minutos y volvé a intentarlo. '
        'También podés probar <a href="/logout">cerrando sesión</a>.')
    )


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Nombre de usuario o DNI'

    def confirm_login_allowed(self, user):
        session_existente = user.fiscal.session_key
        last_seen = user.fiscal.last_seen
        ahora = timezone.now()
        timeout = last_seen + timedelta(seconds=settings.SESSION_TIMEOUT) if last_seen else None
        if session_existente and last_seen and ahora < timeout:
            raise forms.ValidationError(
                _(self.already_logged_message),
                code='already_logged'
            )
        return super().confirm_login_allowed(user)


def opciones_actuales():
    try:
        return Categoria.opciones_actuales().count()
    except Exception:
        return 0


class FiscalForm(forms.ModelForm):

    dni = ARDNIField(required=False)

    class Meta:
        model = Fiscal
        exclude = []


class ReferidoForm(forms.Form):
    url = forms.CharField()
    url.label = ''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['url'].widget.attrs['readonly'] = True



class MisDatosForm(FiscalForm):

    class Meta:
        model = Fiscal
        fields = [
            'nombres',
            'apellido',
            'tipo_dni',
            'dni',
        ]


class FiscalFormSimple(FiscalForm):

    class Meta:
        model = Fiscal
        fields = ['nombres', 'apellido', 'dni']


class CustomModelChoiceField(forms.ModelChoiceField):

    def label_from_instance(self, obj):
        return obj.label_from_instance


class FiscalxDNI(forms.ModelForm):
    dni = ARDNIField(required=True)


class QuieroSerFiscalForm(forms.Form):

    MENSAJE_ERROR_CODIGO_REF = 'Codigo de referido debe ser de 4 letras y/o números.'
    MENSAJE_ERROR_TELEFONO_INVALIDO = 'Teléfono no es válido. Chequeá código de área y teléfono.'
    MENSAJE_ERROR_DNI_REPETIDO = 'Ya se encuentra un usuario registrado con ese DNI.'
    MENSAJE_ERROR_PASSWORD_NO_IGUALES = "Las contraseñas no coinciden."

    CARACTERES_REF_CODIGO = 4
    CANTIDAD_DIGITOS_NUMERACION_ARGENTINA = 10

    MAX_DIGITOS_TELEFONO_LOCAL = 8
    MIN_DIGITOS_TELEFONO_LOCAL = 5
    MAX_DIGITOS_COD_AREA = 5
    MIN_DIGITOS_COD_AREA = 2

    email = forms.EmailField(required=True)
    email_confirmacion = forms.EmailField(required=True, label="Confirmar email")
    apellido = forms.CharField(required=True, label="Apellido", max_length=50)
    nombres = forms.CharField(required=True, label="Nombres", max_length=100)
    dni = ARDNIField(required=True, label="DNI", help_text='Ingresá tu Nº de documento sin puntos.')
    telefono_area = forms.CharField(
        label='Código de área (sin 0 adelante).',
        help_text='Por ejemplo: 11 para CABA, 221 para La Plata, 351 para Córdoba, etc.',
        required=True,
        validators=[
            MaxLengthValidator(MAX_DIGITOS_COD_AREA),
            MinLengthValidator(MIN_DIGITOS_COD_AREA),
        ]
    )
    telefono_local = forms.CharField(
        label='Teléfono',
        help_text='Ingresá tu teléfono sin el 15, ni guiones ni espacios.',
        required=True,
        validators=[
            MaxLengthValidator(MAX_DIGITOS_TELEFONO_LOCAL),
            MinLengthValidator(MIN_DIGITOS_TELEFONO_LOCAL),
        ]
    )

    distrito = forms.ModelChoiceField(
        required=True,
        label='Provincia',
        queryset=Distrito.objects.all().order_by('numero'),
        widget=autocomplete.ModelSelect2(
            url='autocomplete-distrito-simple',
        ),
    )

    seccion = forms.ModelChoiceField(
        queryset=Seccion.objects.all(),
        required=False,
        widget=autocomplete.ModelSelect2(
            url='autocomplete-seccion-simple',
            forward=['distrito']
        ),
    )
    
    referente_nombres = forms.CharField(required=False, label="Nombre del referente", max_length=100)
    referente_apellido = forms.CharField(required=False, label="Apellido del referente", max_length=100)

    referido_por_codigo = forms.CharField(
        required=False,
        label="Código de referencia",
        help_text="Si no sabes qué es, dejalo en blanco."
    )

    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput,
        strip=False,
    )
    password_confirmacion = forms.CharField(
        label=_("Password confirmation"),
        strip=False,
        widget=forms.PasswordInput,
    )

    layout = Layout(
        Fieldset(
            'Datos personales',
            Row('nombres', 'apellido', 'dni'),
            Row('email', 'email_confirmacion'),
            Row('password', 'password_confirmacion'),
            Row('distrito', 'seccion')
        ),
        Fieldset(
            'Teléfono celular',
            Row('telefono_area', 'telefono_local')
        ),
        Fieldset(
            'Referencia',
            Row('referente_nombres', 'referente_apellido', 'referido_por_codigo')
        )
    )

    def clean(self):
        cleaned_data = super().clean()
        self.validar_correo(cleaned_data)
        self.validar_telefono(cleaned_data.get('telefono_area'), cleaned_data.get('telefono_local'))

    def clean_telefono_area(self):
        telefono_area = self.cleaned_data.get('telefono_area')
        if telefono_area:
            # por las dudas, sacamos los 0 a la izquierda del código de área
            telefono_area = telefono_area.lstrip('0')
        return telefono_area

    def validar_correo(self, cleaned_data):
        email = cleaned_data.get('email')
        email2 = cleaned_data.get('email_confirmacion')
        if email and email2 and email != email2:
            self.add_error('email', 'Los emails no coinciden')
            self.add_error('email_confirmacion', 'Los emails no coinciden')

    def validar_telefono(self, telefono_area, telefono_local):
        if telefono_area and telefono_local:
            cantidad_digitos_telefono = len(telefono_area) + len(telefono_local)
            if cantidad_digitos_telefono != self.CANTIDAD_DIGITOS_NUMERACION_ARGENTINA:
                error = (
                    "Revisá el código de área y teléfono."
                    f"Entre ambos deben ser {self.CANTIDAD_DIGITOS_NUMERACION_ARGENTINA} números"
                )
                self.add_error('telefono_area', error)
                self.add_error('telefono_local', error)
            telefono = telefono_area + telefono_local
            valor = phonenumbers.parse(telefono, 'AR')
            if not phonenumbers.is_valid_number(valor):
                self.add_error(
                    'telefono_local',
                    self.MENSAJE_ERROR_TELEFONO_INVALIDO
                )
                self.add_error(
                    'telefono_area',
                    self.MENSAJE_ERROR_TELEFONO_INVALIDO
                )

    def clean_referente_apellido(self):
        return self.cleaned_data.get('referente_apellido', '').strip() or None

    def clean_referente_nombres(self):
        return self.cleaned_data.get('referente_nombres', '').strip() or None

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            password_validation.validate_password(password)
        return password

    def clean_password_confirmacion(self):
        password = self.cleaned_data.get('password')
        password_confirmacion = self.cleaned_data.get('password_confirmacion')
        if password and password_confirmacion:
            if password != password_confirmacion:
                raise forms.ValidationError(self.MENSAJE_ERROR_PASSWORD_NO_IGUALES)
        return password_confirmacion

    def clean_dni(self):
        dni = self.cleaned_data.get('dni')
        if Fiscal.objects.filter(dni=dni).exists():
            raise ValidationError(self.MENSAJE_ERROR_DNI_REPETIDO)
        return dni

    def clean_referido_por_codigo(self):
        referido_por_codigo = self.cleaned_data.get('referido_por_codigo', None)
        if referido_por_codigo:
            if len(referido_por_codigo) != self.CARACTERES_REF_CODIGO:
                raise ValidationError(self.MENSAJE_ERROR_CODIGO_REF)
            referido_por_codigo = referido_por_codigo.upper()
        return referido_por_codigo


class VotoMesaModelForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['carga'].widget = forms.HiddenInput()
        self.fields['carga'].required = False
        self.fields['opcion'].label = ''
        self.fields['opcion'].widget = forms.Select(
            attrs={
                # Materialize muestra el select default
                'class': 'browser-default',
                # Se deshabilita abrir el select
                'onmousedown': '(function(e){ e.preventDefault(); })(event, this)'
            }
        )
        self.fields['votos'].label = ''
        self.fields['votos'].required = False

    class Meta:
        model = VotoMesaReportado
        fields = ('carga', 'opcion', 'votos')


class BaseVotoMesaReportadoFormSet(BaseModelFormSet):

    def __init__(self, *args, **kwargs):
        """
        Se reciben dos parámetros extra, ``mesa`` y  ``datos_previos``, útiles para la
        validación.

        ``mesa`` se utiliza para verificar que la cantidad de votos no supera la cantidad de electores

        ``datos_previos`` es un diccionario en la forma {opcion_id: votos_previos, ...}
        donde viene los valores de una carga parcial u opciones meta, tal cual se presentan
        pre-inicializados en el formset. Acá se reciben para verificar que estos datos
        no fueron adulterados para el requests "POST"
        """
        self.mesa = kwargs.pop('mesa')
        self.datos_previos = kwargs.pop('datos_previos')
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        suma = 0
        for form in self.forms:
            opcion = form.cleaned_data.get('opcion')
            votos = form.cleaned_data.get('votos')
            if not opcion.tipo == Opcion.TIPOS.metadata:
                suma += votos

            previos = self.datos_previos.get(opcion.id, None)
            if previos and previos != votos:
                form.add_error('votos', ValidationError(
                    f'El valor confirmado que tenemos para esta opción es {previos}'
                ))

        errors = []
        if suma > self.mesa.electores:
            errors.append(
                'El total de votos no puede ser mayor a la '
                f'cantidad de electores de la mesa: {self.mesa.electores}'
            )

        if errors:
            form.add_error('votos', ValidationError(errors))


votomesareportadoformset_factory = partial(
    modelformset_factory,
    VotoMesaReportado,
    form=VotoMesaModelForm,
    formset=BaseVotoMesaReportadoFormSet,
    extra=0,
    can_delete=False
)
