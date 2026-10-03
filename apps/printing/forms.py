from django import forms


class DocumentConfigurationForm(forms.Form):
    header = forms.CharField(label="Nome no cabeçalho", max_length=120)
    footer = forms.CharField(label="Texto do rodapé", max_length=500, required=False,
                             widget=forms.Textarea(attrs={"rows": 4}))
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


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
