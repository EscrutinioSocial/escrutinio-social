from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from fiscales.models import Fiscal


class LoggueConMesaForm(forms.Form):
    mesa = forms.IntegerField()


class ReferentesForm(forms.Form):
    referentes = forms.ModelMultipleChoiceField(
        queryset=Fiscal.objects.filter(tipo='general'), required=False,
        widget=FilteredSelectMultiple('Referentes', is_stacked=False)
    )

    class Media:
        css = {
            'all': ['admin/css/widgets.css',
                    'css/uid-manage-form.css'],
        }
        # Adding this javascript is crucial
        js = ['admin/js/vendor/jquery.js',
              'admin/js/jquery.init.js',
              'admin/js/core.js',
              'admin/js/SelectBox.js',
              'admin/js/SelectFilter2.js',
              '/admin/jsi18n/']
