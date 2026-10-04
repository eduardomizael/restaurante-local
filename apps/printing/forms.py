from django import forms

from apps.printing.logos import normalize_logo


class DocumentConfigurationForm(forms.Form):
    logo = forms.FileField(label="Logo do restaurante (opcional, PNG ou JPG, até 2 MB)", required=False,
                           widget=forms.FileInput(attrs={"accept": "image/png,image/jpeg"}))
    remove_logo = forms.BooleanField(label="Remover logo atual", required=False)
    header = forms.CharField(label="Nome no cabeçalho", max_length=120)
    footer = forms.CharField(label="Texto do rodapé", max_length=500, required=False,
                             widget=forms.Textarea(attrs={"rows": 4}))
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    def clean_logo(self):
        """Validate the uploaded image before the settings transaction."""
        upload = self.cleaned_data.get("logo")
        if upload:
            normalize_logo(upload)
        return upload

    def clean(self):
        """Reject conflicting replacement and removal requests."""
        data = super().clean()
        if data.get("logo") and data.get("remove_logo"):
            raise forms.ValidationError("Escolha uma nova logo ou marque a remoção da atual.")
        return data


class FinalizeForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    expected_fingerprint = forms.RegexField(regex=r"\A[0-9a-f]{64}\Z", widget=forms.HiddenInput)
    reviewed_mode = forms.ChoiceField(choices=[("PREVIEW", "Simulação"), ("RAW", "Impressão física")], widget=forms.HiddenInput)
    printer_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


class ReprintForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    confirm = forms.BooleanField(widget=forms.HiddenInput, initial=True)
    reviewed_mode = forms.ChoiceField(choices=[("PREVIEW", "Simulação"), ("RAW", "Impressão física")], widget=forms.HiddenInput)
    printer_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
