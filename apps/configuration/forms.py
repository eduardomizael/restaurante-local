from django import forms
from apps.configuration.models import HardwareConfiguration


class ApplicationConfigurationForm(forms.Form):
    display_name = forms.CharField(label="Nome do restaurante", max_length=80,
                                  help_text="Exibido na barra superior e no título das páginas.")
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


class HardwareConfigurationForm(forms.Form):
    scale_port = forms.CharField(label="Porta da balança", max_length=8)
    scale_protocol = forms.ChoiceField(label="Protocolo da balança", choices=HardwareConfiguration.ScaleProtocol.choices,
                                      help_text="Selecione o mesmo protocolo configurado na balança em [F][3].")
    printer_name = forms.CharField(label="Nome da fila de impressão Windows", max_length=120)
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
