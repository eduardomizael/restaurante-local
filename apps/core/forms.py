"""Parse local runtime interface requests."""

from django import forms


class HistoryAcknowledgmentForm(forms.Form):
    fingerprint = forms.RegexField(regex=r"\A[0-9a-f]{64}\Z", max_length=64)
