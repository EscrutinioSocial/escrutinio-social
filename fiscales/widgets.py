"""A simple alternative for select: an input field is used to query
via AJAX some view; if there is exactly one result, its label is
displayed besides the input and its id is set to the model field.
"""

from django import forms

class Select(forms.widgets.Select):
    pass
