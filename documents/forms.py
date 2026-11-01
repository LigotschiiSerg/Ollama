import os
from django import forms
from django.conf import settings
from .models import Cell


class UploadForm(forms.Form):
    pdf = forms.FileField(required=False,label='PDF-файл')
    url = forms.URLField(required=False,label='Или HTTPS-ссылка на PDF')

    def clean(self):
        cleaned = super().clean()
        if bool(cleaned.get('pdf')) == bool(cleaned.get('url')):
            raise forms.ValidationError('Укажите файл ИЛИ ссылку')
        file = cleaned.get('pdf')
        if file and (file.size > settings.PDF_MAX_BYTES or not file.name.lower().endswith('.pdf')):
            raise forms.ValidationError('Нужен PDF до 20 МБ')
        return cleaned


class CellForm(forms.ModelForm):
    class Meta:
        model = Cell
        fields = ['value']
        widgets = {'value':forms.Textarea(attrs={'rows':3})}
