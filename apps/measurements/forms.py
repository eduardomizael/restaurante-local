"""Parse the explicit capture and catalogue revisions for a product correction."""

from django import forms


class MeasurementProductForm(forms.Form):
    """Require the identities and prices displayed to the operator."""

    product_id = forms.IntegerField(min_value=1)
    expected_revision = forms.IntegerField(min_value=1)
    expected_product_revision = forms.IntegerField(min_value=1)
