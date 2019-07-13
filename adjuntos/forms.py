from django import forms
from .models import Identificacion
from elecciones.models import Mesa, Seccion, Circuito, Distrito


class IdentificacionProblemaForm(forms.ModelForm):

    class Meta:
        model = Identificacion
        fields = ['status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].label = ''
        choices = self.fields['status'].choices
        self.fields['status'].choices = [
            (v, s) for (v, s) in choices if v != Identificacion.STATUS.identificada
        ]


class IdentificacionForm(forms.ModelForm):
    """
    Este formulario se utiliza para asignar mesa
    """
    distrito = forms.ModelChoiceField(queryset=Distrito.objects.all())
    seccion = forms.ModelChoiceField(queryset=Seccion.objects.all())
    circuito = forms.ModelChoiceField(queryset=Circuito.objects.all())
    mesa = forms.ModelChoiceField(queryset=Mesa.objects.all())

    class Meta:
        model = Identificacion
        fields = ['distrito', 'seccion', 'circuito', 'mesa']

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance and instance.mesa:
            kwargs['initial']['circuito'] = circuito = instance.mesa.lugar_votacion.circuito
            kwargs['initial']['seccion'] = seccion = circuito.seccion
            kwargs['initial']['distrito'] = distrito = seccion.distrito
        super().__init__(*args, **kwargs)
        self.fields['distrito'].widget.attrs['autofocus'] = True
        if instance and instance.mesa:
            # si el attach ya estaba clasificado, limitamos los queryset a los
            # de su jerarquia, tal como queda al ir definiendo en cascada.
            self.fields['seccion'].queryset = Seccion.objects.filter(distrito=distrito)
            self.fields['circuito'].queryset = Circuito.objects.filter(seccion=seccion)
            self.fields['mesa'].queryset = Mesa.objects.filter(lugar_votacion__circuito=circuito)
        else:
            # si aun no está clasificado, entonces seccion circuito y empiezan sin opciones
            # y se agregan dinamicamente via ajax cuando se va eligiendo el correspondiente ancestro
            self.fields['seccion'].choices = (('', '---------'),)
            self.fields['circuito'].choices = (('', '---------'),)
            self.fields['mesa'].choices = (('', '---------'),)

    def clean(self):
        cleaned_data = super().clean()
        mesa = cleaned_data.get('mesa')
        circuito = cleaned_data.get('circuito')
        seccion = cleaned_data.get('seccion')
        distrito = cleaned_data.get('distrito')
        if seccion and seccion.distrito != distrito:
            self.add_error(
                'seccion', 'Esta sección no pertenece al distrito'
            )
        elif circuito and circuito.seccion != seccion:
            self.add_error(
                'circuito', 'Este circuito no pertenece a la sección'
            )
        if mesa and mesa.lugar_votacion.circuito != circuito:
            self.add_error(
                'mesa', 'Esta mesa no pertenece al circuito'
            )
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
