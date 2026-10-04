"""Reference-aligned document positions and legacy layout preservation."""

from copy import deepcopy

from django.test import SimpleTestCase
from django.template.loader import render_to_string

from apps.printing.documents import document_bold_lines, preview_parts, render_text
from hardware.printer.escpos import encode_document


class SlipLayoutTests(SimpleTestCase):
    def content(self):
        return {
            "version": 5, "columns": 48, "layout": {"header_scale": 2, "name_columns": 20, "price_columns": 6},
            "header": "Restaurante Primeiro da Serra", "footer": "Volte sempre!", "order_number": 1254,
            "opened_at": "2026-10-04T11:00:00-03:00", "printed_at": "2026-10-04T11:52:53-03:00",
            "items": [
                {"description": "REFEIÇÃO POR KG", "unit": "KG", "unit_price_cents": 5990,
                 "weight_grams": 224, "quantity_units": None, "measurement_id": 1, "total_cents": 1342, "is_meal": True},
                {"description": "REFEIÇÃO À VONTADE", "unit": "UN", "unit_price_cents": 3990,
                 "weight_grams": None, "quantity_units": 2, "measurement_id": None, "total_cents": 7980, "is_meal": True},
            ],
            "manuscript_rows": [{"quantity_units": 1, "weight_grams": 0, "variants": [
                {"description": "COCA COLA 1 LT", "unit": "UN", "unit_price_cents": 1500,
                 "quantity_units": 1, "total_cents": 1500},
            ]}], "subtotal_cents": 10822,
        }

    def test_identity_meals_total_and_footer_match_reference_positions(self):
        content = self.content()
        lines = render_text(content).splitlines()
        identity = next(line for line in lines if line.startswith("COMANDA #"))
        self.assertEqual(identity, "COMANDA #1254".ljust(29) + "04/10/2026 11:52:53")
        meal = next(line for line in lines if line.startswith("REFEIÇÃO POR KG"))
        self.assertEqual(meal, "REFEIÇÃO POR KG".ljust(37) + "R$ 59,90/KG")
        quantity = next(line for line in lines if line.startswith("Pesagem #1"))
        self.assertTrue(quantity.startswith("Pesagem #1 - 0,224 kg"))
        self.assertTrue(quantity.endswith("VALOR R$ 13,42"))
        subtotal = next(line for line in lines if "SUBTOTAL REFEIÇÕES" in line)
        self.assertEqual(subtotal, "SUBTOTAL REFEIÇÕES R$ 93,22".rjust(48))
        self.assertEqual(lines[-1], "Volte sempre!".center(48))
        self.assertLessEqual(max(map(len, lines)), 48)
        for removed in ("COMANDA ABERTA", "Finalização:", "Impressão:", "PRÉ-INSERIDO",
                        "ACRÉSCIMOS MANUSCRITOS", "[X] =", "Preenchimento manual"):
            self.assertNotIn(removed, "\n".join(lines))
        total = lines.index("TOTAL A PAGAR R$ ______________________".center(48))
        self.assertEqual(lines[total - 2:total], ["", ""])
        self.assertEqual(lines[total + 1:total + 4], ["", "", ""])

    def test_header_preview_boundaries_and_second_copy_use_same_text(self):
        content = self.content()
        parts = preview_parts(content)
        self.assertEqual(parts["slip_header_scale"], 2)
        self.assertEqual(parts["slip_header"] + parts["slip_body"], render_text(content))
        self.assertIn("SEGUNDA VIA", render_text(content, second_copy=True))
        self.assertNotIn("SEGUNDA VIA", render_text(content))

    def test_long_descriptions_prices_and_quantity_overflow_preserve_paper_width(self):
        content = self.content()
        content["items"][0]["description"] = "REFEIÇÃO COM UMA DESCRIÇÃO BEM LONGA PARA ENVOLVER LINHAS"
        content["items"][0]["unit_price_cents"] = 9_000_000_000_000
        content["manuscript_rows"][0]["variants"][0]["quantity_units"] = 9
        text = render_text(content)
        self.assertIn("Quantidade lançada: 9 UN", text)
        self.assertIn("90000000000,00/KG", text)
        self.assertLessEqual(max(map(len, text.splitlines())), 48)

    def test_version_four_retains_its_original_labels_and_spacing(self):
        content = deepcopy(self.content())
        content["version"] = 4
        text = render_text(content)
        self.assertIn("COMANDA ABERTA", text)
        self.assertIn("Impressão: 2026-10-04T11:52:53-03:00", text)
        self.assertIn("ACRÉSCIMOS MANUSCRITOS", text)
        self.assertIn("SUBTOTAL PRÉ-INSERIDO", text)
        self.assertIn("[X] = unidade já lançada", text)

    def test_version_six_emphasizes_only_meal_subtotal_in_preview_and_raw(self):
        content = self.content()
        legacy_text = render_text(content)
        self.assertEqual(document_bold_lines(content), ())
        content["version"] = 6
        self.assertEqual(render_text(content), legacy_text)
        for second_copy in (False, True):
            text = render_text(content, second_copy=second_copy)
            parts = preview_parts(content, second_copy=second_copy)
            indexes = document_bold_lines(content, second_copy=second_copy)
            self.assertEqual(len(indexes), 1)
            subtotal = text.splitlines(keepends=True)[indexes[0]]
            self.assertIn("SUBTOTAL REFEIÇÕES R$ 93,22", subtotal)
            html = render_to_string("printing/slip.html", parts)
            self.assertIn("<strong>" + subtotal + "</strong>", html)
            self.assertEqual(html.count("<strong>"), 1)
            payload = encode_document(text, header_lines=len(parts["slip_header"].splitlines()),
                                      header_scale=2, bold_lines=indexes)
            self.assertIn(b"\x1bE\x01" + subtotal.encode("cp860") + b"\x1bE\x00", payload)
            self.assertEqual(payload.count(b"\x1bE\x01"), 1)
