from django import forms


class ImportTalksForm(forms.Form):
    start = forms.IntegerField(min_value=0, help_text='The index of the first day')
    end = forms.IntegerField(min_value=0, help_text='The index of the last day')
    file = forms.FileField()
