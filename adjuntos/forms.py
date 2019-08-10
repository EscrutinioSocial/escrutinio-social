from django import forms
from django.conf import settings
from django.core.validators import FileExtensionValidator, ValidationError
from django.db.models import Q
from annoying.functions import get_object_or_None

from .models import Identificacion, PreIdentificacion, Attachment
from elecciones.models import Mesa, Seccion, Circuito, Distrito
from problemas.models import ReporteDeProblema

from .widgets import Select

MENSAJES_ERROR = {
    'distrito' : '',
    'seccion': 'Esta sección no pertenece al distrito',
    'circuito': 'Este circuito no pertenece a la sección',
    'mesa': 'Esta mesa no pertenece al circuito'
}
    
    

class SelectField(forms.ModelChoiceField):

    widget = Select
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.name = kwargs.get('label',self.queryset.model._meta.object_name)
        required = kwargs.get('required',True)
        self.widget.attrs['required'] = required
    
    def clean(self,value):
        if value == "" or value == -1 or value == "-1":
            return None
        return super().clean(value)

    
class CharFieldModel(forms.CharField):

    def queryset(self,value,*args):
        query = {self.predicate: value}
        return self.model.objects.filter(*args,**query)
    
    def __init__(self,model,predicate,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.model = model
        self.predicate = predicate
        self.label = kwargs.get('label',self.model._meta.object_name)


    def get_object(self,value,*args):
        datum = super().clean(value)
        objs = self.queryset(datum,*args)
        if len(objs) != 1:
            return None
        return objs[0]
        
class IdentificacionForm(forms.ModelForm):
    """
    Este formulario se utiliza para asignar mesa
    """

    distrito = SelectField(
        queryset = Distrito.objects.all(),
    )

    seccion = CharFieldModel(
        model = Seccion,
        predicate = 'numero__iexact',
        label = 'Sección',
    )
    
    circuito = CharFieldModel(
        model = Circuito,
        predicate = 'numero__iexact',
    )

    mesa = CharFieldModel(
        model = Mesa,
        predicate = 'numero__iexact'
    )

    class Meta:
        model = Identificacion
        fields = ['distrito','seccion','circuito','mesa']

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance and instance.mesa:
            kwargs['initial']['circuito'] = circuito = instance.mesa.lugar_votacion.circuito
            kwargs['initial']['seccion'] = seccion = circuito.seccion
            kwargs['initial']['distrito'] = distrito = seccion.distrito
        super().__init__(*args, **kwargs)

    def clean(self):
        self.cleaned_data = {}
        mesa_nro = self.data['mesa']
        circuito_nro = self.data['circuito']
        seccion_nro = self.data['seccion']
        distrito = self.fields['distrito'].clean(self.data['distrito'])
        seccion = self.fields['seccion'].get_object(seccion_nro,Q(distrito=distrito))
        self.cleaned_data['distrito'] = distrito
        if seccion is not None:
            self.cleaned_data['seccion'] = seccion
        else:
            self.add_error(
                'seccion', MENSAJES_ERROR['seccion']
            )
        circuito = self.fields['circuito'].get_object(circuito_nro,Q(seccion=seccion))
        if circuito is not None:
            self.cleaned_data['circuito'] = circuito
        else:
            self.add_error(
                'circuito', MENSAJES_ERROR['circuito']
            )
        mesa = self.fields['mesa'].get_object(mesa_nro,Q(circuito=circuito))
        if mesa is not None:
            self.cleaned_data['mesa'] = mesa
        else:
            self.add_error(
                'mesa', MENSAJES_ERROR['mesa']
            )
        return self.cleaned_data

class PreIdentificacionForm(forms.ModelForm):
    """
    Este formulario se utiliza para asignar una pre identificación a un adjunto.
    """
    distrito = SelectField(
        queryset = Distrito.objects.all(),
    )

    seccion = SelectField(
         required = False,
         queryset = Seccion.objects.all(),
         label = 'Sección',
    )
    
    circuito = SelectField(
         required = False,
         queryset = Circuito.objects.all(),
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
                'seccion', MENSAJES_ERROR['seccion']
            )
        if circuito and circuito.seccion != seccion:
            self.add_error(
                'circuito', MENSAJES_ERROR['circuito']
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

