from django import forms
from .models import Attachment
from elecciones.models import Mesa


class AsignarMesaForm(forms.ModelForm):
    """
    Este formulario se utiliza para asignar mesa
    o reportar un problema a una foto.
    """

    # FIXME revisar si hay numero de mesas repetidas
    mesa = forms.IntegerField(
        label='Nº Mesa',
        required=False,
        help_text='A que número pertenece esta acta'
    )
    mesa_confirm = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Attachment
        fields = ['mesa', 'problema', 'mesa_confirm']

    def __init__(self, *args, **kwargs):
        # Dado que el campo ``mesa`` es un entero que refiere al "numero" de mesa (y no el ID)
        # del objeto, para el caso de edición de un objeto preexistente, se cambia
        # el valor
        if kwargs['instance'] and kwargs['instance'].mesa:
            kwargs['initial']['mesa'] = kwargs['instance'].mesa.numero
        super().__init__(*args, **kwargs)

        self.fields['mesa'].widget.attrs['tabindex'] = 1
        self.fields['mesa'].widget.attrs['autofocus'] = True
        self.fields['problema'].widget.attrs['tabindex'] = 99

    def clean_mesa(self):
        """
        Verifica que el número entero ingresado corresponda con un número de mesa
        válido
        """
        numero = self.cleaned_data['mesa']
        if not numero:
            return numero
        try:
            mesa = Mesa.objects.get(numero=numero)
        except Mesa.DoesNotExist:
            raise forms.ValidationError('No existe una mesa con este número. ')
        return mesa.numero

    def clean(self):
        """
        Valida la exclusión mutua entre un numero de mesa y un problema
        Si se clasifica con un numero de mesa, no puede reportarse un problema

        Además existe un caso de "advertencia" al usuario cuando una mesa ya tiene un documento
        conocido asociado por las dudas se trate de un erro de carga y no un documento efectivamente
        distinto para la misma mesa. Si se intenta guardar, se reporta un aviso. Si el usuario vuelve
        a guardar, entonces el documento se confirma para esa mesa.
        """

        cleaned_data = super().clean()
        problema = cleaned_data.get('problema')
        mesa_numero = cleaned_data.get('mesa')
        mesa_confirm = cleaned_data.get('mesa_confirm')

        if not mesa_numero and not problema:

            self.add_error(
                'mesa', 'Indicá la mesa o reportá un problema. '
            )

        elif problema and mesa_numero:
            cleaned_data['mesa'] = None
            self.add_error(
                'problema', 'Dejá el número en blanco si hay un problema. '
            )

        if mesa_numero and Attachment.objects.filter(
            mesa__numero=mesa_numero
        ).exists() and mesa_numero != mesa_confirm:
            # Se reporta un "warning"
            # Si se guarda de nuevo se cumplirá que ``mesa_numero == mesa_confirm``
            # y por lo tanto los datos serán válidos y no se reportará el warning
            self.data._mutable = True    # necesario para poder modificar los datos crudos
            self.data['mesa_confirm'] = mesa_numero
            self.data._mutable = False
            self.add_error(
                'mesa', 'Esta mesa ya tiene una o más imágenes adjuntas. Revisá y guardá de nuevo para confirmar .'
            )

        cleaned_data['mesa'] = Mesa.objects.get(numero=mesa_numero)
        return cleaned_data


class AgregarAttachmentsForm(forms.Form):
    """
    Form para subir uno o más archivos para ser asociados a instancias de
    :py:class:`adjuntos.Attachment`
    """

    file_field = forms.FileField(
        label="Archivo/s",
        widget=forms.ClearableFileInput(attrs={'multiple': True})
    )
