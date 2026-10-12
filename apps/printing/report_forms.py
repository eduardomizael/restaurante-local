"""Parse report periods and explicitly reviewed thermal print requests."""

from django import forms

from apps.printing.forms import ReprintForm


class PeriodForm(forms.Form):
    start = forms.DateField(label="Data inicial", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    end = forms.DateField(label="Data final", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))

    def clean(self):
        """Require an inclusive, ordered period of at most one leap year."""
        data = super().clean()
        if data.get("start") and data.get("end"):
            if data["end"] < data["start"]:
                raise forms.ValidationError("A data final deve ser igual ou posterior à inicial.")
            elif (data["end"] - data["start"]).days >= 366:
                raise forms.ValidationError("Selecione no máximo 366 dias por consulta.")
        return data


class TotalsForm(PeriodForm):
    mode = forms.ChoiceField(label="Apresentação", choices=[("period", "Total no período"), ("daily", "Diário")])


class ReportPrintForm(ReprintForm):
    snapshot = forms.CharField(widget=forms.HiddenInput)
    selection = forms.CharField(max_length=10, widget=forms.HiddenInput)
