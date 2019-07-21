from django import forms
from elecciones.models import Mesa, Seccion, Circuito, Distrito
from .models import ReporteDeProblema

class IdentificacionDeProblemaForm(forms.ModelForm):
    class Meta:
        model = ReporteDeProblema
        fields = ['tipo_de_problema','descripcion']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = self.fields['tipo_de_problema'].choices
        self.fields['tipo_de_problema'] = forms.ChoiceField(widget=forms.RadioSelect,
                                                            choices=choices,
                                                            label='')
        self.fields['descripcion'] = forms.CharField(label='Descripción', max_length=100)


