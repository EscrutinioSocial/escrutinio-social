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
    'mesa': 'Esta mesa no pertenece al circuito',
    'circuito_mesa' : 'Esta mesa no existe en el circuito',
    'seccion_mesa' : 'Esta mesa no existe en la sección',
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

    def clean(self,value):
        if value == "" or value == "-1":
            return None
        return super().clean(value)

    def get_object(self,value,*args):
        datum = super().clean(value)
        objs = self.queryset(datum,*args).distinct()
        if objs.count() != 1:
            return None
        return objs[0]
        
class IdentificacionForm(forms.ModelForm):
    """
    Este formulario se utiliza para asignar mesa
    """

    distrito = SelectField(
        queryset = Distrito.objects.all(),
        help_text = "Puede ingresar número o nombre",
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



    def check_seccion(self,distrito,mesa=None):
        seccion_nro = self.fields['seccion'].clean(self.data['seccion'])
        seccion = None
        
        if seccion_nro is not None:
            # la busco en el distrito
            lookup = Q(distrito_id=distrito.id)
            seccion = self.fields['seccion'].get_object(seccion_nro,lookup)
            if seccion is None:
                # no lo encontré, la seccion no pertenece al distrito
                self.add_error('seccion', MENSAJES_ERROR['seccion'])
            return seccion

        # sólo lo puedo encontrar gracias a la mesa.
        if mesa is None:
            self.add_error('seccion', MENSAJES_ERROR['seccion'])
            return None
        
        seccion = mesa.circuito.seccion
        if seccion and seccion.distrito != distrito:
            self.add_error('seccion', MENSAJES_ERROR['seccion'])
        else:
            return seccion

        
    def check_circuito(self,distrito,mesa=None,seccion=None):
        circuito_nro = self.fields['circuito'].clean(self.data['circuito'])

        circuito = None
        if circuito_nro is not None and seccion is not None:
            # lo busco en la sección
            lookup = Q(seccion__distrito=distrito,seccion=seccion)
            circuito = self.fields['circuito'].get_object(circuito_nro,lookup)
            if circuito is None:
                # no lo encontré, el circuito no pertenece a la sección
                self.add_error('circuito', MENSAJES_ERROR['circuito'])
            return circuito

        # Si no tengo sección, sólo lo puedo encontrar gracias a la mesa.
        if mesa is None:
            self.add_error('circuito', MENSAJES_ERROR['circuito'])
            return None
        
        circuito = mesa.circuito
        if seccion and circuito.seccion != seccion:
            self.add_error('circuito', MENSAJES_ERROR['circuito'])
        else:
            return circuito
            
    def check_seccion_circuito(self,distrito,mesa=None):
        seccion = self.check_seccion(distrito, mesa)
        circuito = self.check_circuito(distrito, mesa, seccion)
        return (seccion, circuito)
        
    def clean(self):
        self.cleaned_data = {}
        mesa_nro = self.data['mesa']
        seccion_nro = self.fields['seccion'].clean(self.data['seccion'])
        circuito_nro = self.fields['circuito'].clean(self.data['circuito'])
        
        # distrito es un SelectField y nos devuelve un distrito posta.
        distrito = self.fields['distrito'].clean(self.data['distrito'])

        # si no tenemos el distrito no podemos seguir.
        if distrito is None:
            self.add_error('distrito', MENSAJES_ERROR['distrito'])
            return self.cleaned_data

        self.cleaned_data['distrito'] = distrito


        ## Intentamos obtener la mesa con distrito y numero de mesa
        lookup_mesa = Q(circuito__seccion__distrito=distrito)
        if seccion_nro:
            lookup_mesa &= Q(circuito__seccion__numero=seccion_nro)
            
        if circuito_nro:
            lookup_mesa &= Q(circuito__numero=circuito_nro)            
        mesa = self.fields['mesa'].get_object(mesa_nro,lookup_mesa)

        ## Intetamos obtener la seccion y circuito con lo que tengamos
        ## a nuestra disposición (distrito, mesa ó los valores del form).
        seccion, circuito = self.check_seccion_circuito(distrito,mesa)

        if seccion:
            self.cleaned_data['seccion'] = seccion
        if circuito:
            self.cleaned_data['circuito'] = circuito

        if mesa:
            if circuito and mesa.circuito != circuito:
                self.add_error('mesa', MENSAJES_ERROR['mesa'])
            else:
                self.cleaned_data['mesa'] = mesa
        else:
            self.add_error('mesa', MENSAJES_ERROR['mesa'])

        return self.cleaned_data

class PreIdentificacionForm(forms.ModelForm):
    """
    Este formulario se utiliza para asignar una pre identificación a un adjunto.
    """
    distrito = SelectField(
        queryset = Distrito.objects.all(),
        help_text = "Puede ingresar número o nombre",
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

