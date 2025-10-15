"""A simple alternative for select: an input field is used to query
via AJAX some view; if there is exactly one result, its label is
displayed besides the input and its id is set to the model field.
"""

from django import forms

class Select(forms.widgets.Input):
    template_name = 'fields/select.html'
    input_type = 'text'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['type'] = self.input_type
        return context

    def required(self,value):
        self.required = value
