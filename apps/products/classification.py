"""Compatibility for historical snapshots created before explicit meal grouping."""

import unicodedata


def legacy_meal_classification(description, unit):
    """Preserve the former rule only for snapshots without a recorded meal flag.

    Args:
        description: Historical product description from the snapshot.
        unit: Historical UN or KG unit.

    Returns:
        bool: Meal classification used before the catalogue had an explicit field.
    """
    name = " ".join(unicodedata.normalize("NFKD", description).encode("ascii", "ignore")
                    .decode("ascii").upper().split())
    return unit == "KG" or name.startswith("REFEICAO ") or name == "REFEICAO" or name.startswith("A VONTADE")
