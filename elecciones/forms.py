from django import forms

from elecciones.models import Seccion
from scheduling.models import mapa_prioridades_default_categoria, mapa_prioridades_default_seccion


class CategoriaForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        prioridad_default = mapa_prioridades_default_categoria().registros_ordenados()[0].prioridad
        self.fields['prioridad'].label = 'Prioridad para la carga'
        self.fields['prioridad'].help_text = f'Valor por defecto: {prioridad_default}'


class SeccionForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # se chequea si las keys de prioridades están seteadas en el formulario
        # para poder setearles label y help_text
        keys_prioridades = [
            'prioridad_hasta_2',
            'prioridad_2_a_10',
            'prioridad_10_a_100',
            'cantidad_minima_prioridad_hasta_2'
        ]

        if set(keys_prioridades).issubset(self.fields.keys()):
            prioridades_default = mapa_prioridades_default_seccion()
            prioridad_default_hasta_2 = prioridades_default.registros_ordenados()[0].prioridad
            prioridad_default_2_a_10 = prioridades_default.registros_ordenados()[1].prioridad
            prioridad_default_10_a_100 = prioridades_default.registros_ordenados()[2].prioridad
            cantidad_minima_prioridad_hasta_2_default = prioridades_default.registros_ordenados()[0].hasta_cantidad
            if (cantidad_minima_prioridad_hasta_2_default is None):
                cantidad_minima_prioridad_hasta_2_default = 'tomar el 2% del circuito independientemente de la cantidad de mesas'
            self.fields['prioridad_hasta_2'].label = 'Prioridad para el primer 2% de las mesas ...'
            self.fields['prioridad_hasta_2'].help_text = f'en cada circuito. Valor por defecto: {prioridad_default_hasta_2}'
            self.fields['prioridad_2_a_10'].label = 'Prioridad desde el 2% hasta el 10% de las mesas ...'
            self.fields['prioridad_2_a_10'].help_text = f'en cada circuito. Valor por defecto: {prioridad_default_2_a_10}'
            self.fields['prioridad_10_a_100'].label = 'Prioridad a partir del 10% de las mesas ...'
            self.fields['prioridad_10_a_100'].help_text = f'en cada circuito. Valor por defecto: {prioridad_default_10_a_100}'
            self.fields['cantidad_minima_prioridad_hasta_2'].label = 'Cantidad mínima de mesas con máxima prioridad ...'
            self.fields['cantidad_minima_prioridad_hasta_2'].help_text = f'... aunque supere el 2% del circuito. Valor por defecto: {cantidad_minima_prioridad_hasta_2_default}'
