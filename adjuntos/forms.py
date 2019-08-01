from django import forms
from django.conf import settings
from django.core.validators import FileExtensionValidator

from .models import Identificacion, PreIdentificacion, Attachment
from elecciones.models import Mesa, Seccion, Circuito, Distrito
from problemas.models import ReporteDeProblema
from dal import autocomplete


class IdentificacionForm(forms.ModelForm):
    """
    Este formulario se utiliza para asignar mesa
    """
    distrito = forms.ModelChoiceField(
        queryset = Distrito.objects.all(),
        widget = autocomplete.ModelSelect2(
            url = 'autocomplete-distrito',
            attrs = {
                'data-minimum-input-length': 1,
            },
        )
    )
    
    seccion = forms.ModelChoiceField(
        queryset = Seccion.objects.all(),
        widget = autocomplete.ModelSelect2(
            url = 'autocomplete-seccion',
            attrs = {
                'data-minimum-input-length': 2,
            },
            forward = ['distrito','circuito','mesa']
        )
    )
    
    circuito = forms.ModelChoiceField(
        queryset = Circuito.objects.all(),
        widget = autocomplete.ModelSelect2(
            url = 'autocomplete-circuito',
            attrs = {
                'data-minimum-input-length': 2,
            },
            forward = ['distrito','seccion','mesa']
        )
    )
    
    mesa = forms.ModelChoiceField(
        queryset = Mesa.objects.all(),
        widget = autocomplete.ModelSelect2(
            url = 'autocomplete-mesa',
            attrs = {
                'data-minimum-input-length': 1,
                'onChange': 'updateCircuito();updateSeccion();',
            },
            forward = ['distrito','seccion','circuito']
        )
    )
    

    
    class Meta:
        model = Identificacion
        fields = ['distrito','mesa','seccion','circuito']
        
    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance and instance.mesa:
            kwargs['initial']['circuito'] = circuito = instance.mesa.lugar_votacion.circuito
            kwargs['initial']['seccion'] = seccion = circuito.seccion
            kwargs['initial']['distrito'] = distrito = seccion.distrito
        super().__init__(*args, **kwargs)


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


class PreIdentificacionForm(forms.ModelForm):
    """
    Este formulario se utiliza para asignar una pre identificación a un adjunto.
    """
    distrito = forms.ModelChoiceField(
        queryset=Distrito.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='autocomplete-distrito',
            attrs={
                'data-minimum-input-length': 3,
            },
        )
    )
    
    seccion = forms.ModelChoiceField(
        queryset=Seccion.objects.all(),
        required=False,
        widget=autocomplete.ModelSelect2(
            url='autocomplete-seccion',
            forward=['distrito']
        )
    )
    
    circuito = forms.ModelChoiceField(
        queryset=Circuito.objects.all(),
        required=False,
        widget=autocomplete.ModelSelect2(
            url='autocomplete-circuito',
            forward=['seccion']
        )
    )

    class Meta:
        model = PreIdentificacion
        fields = ['distrito', 'seccion', 'circuito']

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance:
            kwargs['initial']['circuito'] = circuito = circuito
            kwargs['initial']['seccion'] = seccion = circuito.seccion
            kwargs['initial']['distrito'] = distrito = seccion.distrito
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
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
        return cleaned_data


class BaseUploadForm(forms.Form):
    file_field = forms.FileField(label="Imágenes/s")

    def __init__(self, *args, **kwargs):
        es_multiple = kwargs.pop('es_multiple') if 'es_multiple' in kwargs else True
        super().__init__(*args, **kwargs)
        self.fields['file_field'].widget.attrs.update({'multiple': es_multiple})

    def clean_file_field(self):
        files = self.files.getlist('file_field')
        errors = []
        for content in files:
            if content.size > settings.MAX_UPLOAD_SIZE:
                errors.append(forms.ValidationError(f'Archivo {content.name} demasiado grande'))
        if errors:
            raise forms.ValidationError(errors)
        return files


class AgregarAttachmentsForm(BaseUploadForm):
    """
    Form para subir uno o más archivos para ser asociados a instancias de
    :py:class:`adjuntos.Attachment`

    Se le puede pasar por kwargs si el form acepta múltiples archivos o uno solo.
    """
    file_field = forms.ImageField(label="Imagen/es")


class AgregarAttachmentsCSV(BaseUploadForm):
    """
    Form para subir uno o más archivos CSV.
    """
    file_field = forms.FileField(label="Archivos .csv", validators=[FileExtensionValidator(allowed_extensions=['csv'])])

