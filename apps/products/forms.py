"""Locale-aware parsing into integer commercial units."""

import re
from decimal import Decimal

from django import forms

from apps.core.domain import MAX_MONEY_CENTS
from apps.products.models import Product


class ScaledDecimalField(forms.CharField):
    """Parse decimal text without float, grouping separators or exponent syntax."""

    def __init__(self, *, decimal_places, minimum=0, maximum=MAX_MONEY_CENTS, **kwargs):
        self.decimal_places = decimal_places
        self.minimum = minimum
        self.maximum = maximum
        super().__init__(**kwargs)
        self.widget.attrs.update({"inputmode": "decimal", "autocomplete": "off"})
        self.widget.attrs["data-keypad"] = str(decimal_places)

    def clean(self, value):
        """Convert validated decimal text to integer cents or grams."""
        text = super().clean(value)
        if not text and not self.required:
            return None
        pattern = rf"[0-9]+(?:[.,][0-9]{{1,{self.decimal_places}}})?"
        if len(text) > 20 or re.fullmatch(pattern, text) is None:
            raise forms.ValidationError(f"Informe número sem separador de milhar, com até {self.decimal_places} casas decimais.")
        result = int(Decimal(text.replace(",", ".")) * (10 ** self.decimal_places))
        if not self.minimum <= result <= self.maximum:
            raise forms.ValidationError("Valor fora do intervalo permitido.")
        return result


class ProductForm(forms.Form):
    description = forms.CharField(label="Descrição", max_length=120)
    unit = forms.ChoiceField(label="Unidade", choices=Product.Unit.choices)
    unit_price_cents = ScaledDecimalField(label="Preço unitário / kg (R$)", decimal_places=2)
    active = forms.BooleanField(label="Ativo", required=False, initial=True)
    is_scale_product = forms.BooleanField(label="Produto da balança", required=False)
    is_quick_access = forms.BooleanField(label="Acesso rápido", required=False)
    appears_on_order_slip = forms.BooleanField(label="Aparece na comanda", required=False)
    quick_access_order = forms.IntegerField(label="Ordem rápida", min_value=0, initial=0)
    slip_order = forms.IntegerField(label="Ordem no papel", min_value=0, initial=0)
    expected_revision = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("quick_access_order", "slip_order"):
            self.fields[name].widget.attrs.update({"inputmode": "numeric", "data-keypad": "0"})
