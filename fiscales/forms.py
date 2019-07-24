from functools import partial
from django import forms
from django.forms import modelformset_factory, BaseModelFormSet
from material import Layout, Row, Fieldset
from .models import Fiscal
from elecciones.models import VotoMesaReportado, Categoria, Opcion, Distrito
from localflavor.ar.forms import ARDNIField
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import ugettext_lazy as _
from django.core.validators import ValidationError
from contacto.forms import validar_telefono
import phonenumbers


class AuthenticationFormCustomError(AuthenticationForm):
    error_messages = {
        'invalid_login': (
            'Por favor introduzca un nombre de usuario y una contraseña correctos. '
            'Prueba tu DNI o teléfono sin puntos, guiones ni espacios.'
        ),
        'inactive':
        _("This account is inactive."),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Nombre de usuario o DNI'


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


class FiscalForm(forms.ModelForm):

    dni = ARDNIField(required=False)

    class Meta:
        model = Fiscal
        exclude = []


class QuieroSerFiscalForm(forms.Form):

    CARACTERES_REF_CODIGO = 4

    email = forms.EmailField(required=True)
    email_confirmacion = forms.EmailField(required=True, label="Confirmar email")
    apellido = forms.CharField(required=True, label="Apellido", max_length=50)
    nombres = forms.CharField(required=True, label="Nombres", max_length=100)
    dni = ARDNIField(required=True, label="DNI", help_text='Ingresá tu Nº de documento')
    telefono = forms.CharField(label='Teléfono', help_text='Preferentemente celular')

    distrito = forms.ModelChoiceField(
        required=True,
        label='Provincia',
        queryset=Distrito.objects.all().order_by('numero')
    )

    seccion_autocomplete = forms.CharField(label="Departamento o Municipio",
                                           widget=forms.TextInput(attrs={
                                               'class': 'autocomplete',
                                               'id': 'seccion-autocomplete',
                                               'autocomplete': 'off',
                                               'required': True,
                                           }))
    seccion = forms.CharField(widget=forms.HiddenInput(attrs={'id': 'seccion', 'name': 'seccion'}))
    referido_por_nombres = forms.CharField(required=False, label="Referido por", max_length=100)
    referido_por_codigo = forms.CharField(
        required=False,
        label="Código de referencia",
        help_text="Si no sabes qué es, dejalo en blanco"
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
            'telefono',
            Row('distrito', 'seccion_autocomplete')
        ),
        Fieldset(
            'Referencia',
            Row('referido_por_nombres', 'referido_por_codigo')
        )
    )

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        email2 = cleaned_data.get('email_confirmacion')
        if email and email2 and email != email2:
            self.add_error('email', 'Los emails no coinciden')
            self.add_error('email_confirmacion', 'Los emails no coinciden')

    def clean_telefono(self):
        valor = self.cleaned_data['telefono']
        try:
            valor = validar_telefono(valor)
        except (AttributeError, phonenumbers.NumberParseException):
            raise forms.ValidationError('No es un teléfono válido')
        return valor

    def clean_password_confirmacion(self):
        password = self.cleaned_data.get('password')
        password_confirmacion = self.cleaned_data.get('password_confirmacion')
        if password and password_confirmacion:
            if password != password_confirmacion:
                raise forms.ValidationError("Las contraseñas no coinciden")
        return password_confirmacion

    def clean_dni(self):
        dni = self.cleaned_data.get('dni')
        if Fiscal.objects.filter(dni=dni).exists():
            raise ValidationError('Ya se encuentra un usuario registrado con ese dni')
        return dni

    def clean_referido_por_codigo(self):
        referido_por_codigo = self.cleaned_data.get('referido_por_codigo', None)
        if referido_por_codigo:
            if len(referido_por_codigo) != self.CARACTERES_CODIGO_REFERIDO:
                raise ValidationError('Codigo de referido debe ser de 4 letras y/o números')


class VotoMesaModelForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['carga'].widget = forms.HiddenInput()
        self.fields['carga'].required = False
        self.fields['opcion'].label = ''
        self.fields['votos'].label = ''
        self.fields['votos'].required = False

    class Meta:
        model = VotoMesaReportado
        fields = ('carga', 'opcion', 'votos')


class BaseVotoMesaReportadoFormSet(BaseModelFormSet):

    def __init__(self, *args, **kwargs):
        self.mesa = kwargs.pop('mesa')
        super().__init__(*args, **kwargs)
        self.warnings = []

    def clean(self):
        super().clean()
        suma = 0
        positivos = 0
        total = 0
        form_opcion_total = None
        for form in self.forms:
            if not form.cleaned_data.get('opcion').tipo == Opcion.TIPOS.metadata:
                suma += form.cleaned_data.get('votos') or 0

        # if suma > positivos:
        #     #form_opcion_total.add_error(
        #     #    'votos', 'La sumatoria no se corresponde con el total'
        #     #)
        #     form_opcion_positivos.add_error('votos',
        #         f'Positivos deberia ser igual o mayor a {suma}')

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
