from django import forms

from apps.products.forms import ScaledDecimalField


class ManualItemForm(forms.Form):
    order_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    product_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    quantity_units = forms.IntegerField(label="Quantidade", min_value=1, max_value=100_000, required=False)
    weight_grams = ScaledDecimalField(label="Peso (kg)", decimal_places=3, minimum=1, maximum=1_000_000, required=False)

    def __init__(self, *args, unit=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["quantity_units"].widget.attrs.update({"inputmode": "none", "data-keypad": "0"})
        if unit == "KG":
            self.fields.pop("quantity_units")
            self.fields["weight_grams"].required = True
        elif unit == "UN":
            self.fields.pop("weight_grams")
            self.fields["quantity_units"].required = True


class MeasurementItemForm(forms.Form):
    order_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    measurement_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    request_key = forms.UUIDField(widget=forms.HiddenInput)


class OpenOrderForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)


class RemoveItemForm(forms.Form):
    order_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    item_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class ConfirmationForm(forms.Form):
    confirm = forms.BooleanField(widget=forms.HiddenInput, initial=True)


class NextNumberForm(forms.Form):
    number = forms.IntegerField(label="Número da próxima comanda", min_value=1, max_value=2_147_483_647,
                                widget=forms.NumberInput(attrs={"inputmode": "none", "data-keypad": "0"}))
