from django import forms


class HardwareConfigurationForm(forms.Form):
    scale_port = forms.CharField(label="Porta da balança", max_length=8)
    printer_name = forms.CharField(label="Nome da fila de impressão Windows", max_length=120)
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
