from django import forms

from apps.products.forms import ScaledDecimalField


class ManualItemForm(forms.Form):
    order_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    product_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    quantity_units = forms.IntegerField(label="Quantidade", min_value=1, max_value=100_000, required=False)
    weight_grams = ScaledDecimalField(label="Peso (kg)", decimal_places=3, minimum=1, maximum=1_000_000, required=False)


class MeasurementItemForm(forms.Form):
    order_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    measurement_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    request_key = forms.UUIDField(widget=forms.HiddenInput)
