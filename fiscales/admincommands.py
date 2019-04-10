import shutil
import tempfile

from admincommand.models import AdminCommand


from django import forms


class ImportarFiscales(AdminCommand):

    class form(forms.Form):
        csv = forms.FileField()

    def get_command_arguments(self, forms_data, user):
        fd, path = tempfile.mkstemp()
        with open(path, 'wb') as w:
            shutil.copyfileobj(forms_data['csv'], w)

        return [path], {}


class Dbbackup(AdminCommand):

    class form(forms.Form):
        opciones = forms.CharField(initial='-z', widget=forms.HiddenInput())

    def get_command_arguments(self, forms_data, user):
        flags = forms_data['opciones']
        return [flags], {}

