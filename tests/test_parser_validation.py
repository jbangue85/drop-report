import io
import unittest

import openpyxl

from app.parser import (
    InvalidCarteraFileError,
    InvalidDropiFileError,
    InvalidMetaFileError,
    parse_cartera_xlsx,
    parse_meta_csv,
    parse_xlsx,
)


def build_xlsx(headers, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)

    out = io.BytesIO()
    wb.save(out)
    wb.close()
    return out.getvalue()


class DropiParserValidationTests(unittest.TestCase):
    def test_accepts_ordenes_productos_structure(self):
        headers = [
            "ID",
            "FECHA",
            "NOMBRE CLIENTE",
            "TELÉFONO",
            "NÚMERO GUIA",
            "ESTATUS",
            "DEPARTAMENTO DESTINO",
            "CIUDAD DESTINO",
            "DIRECCION",
            "TRANSPORTADORA",
            "TOTAL DE LA ORDEN",
            "PRODUCTO ID",
            "PRODUCTO",
            "CANTIDAD",
            "PRECIO PROVEEDOR X CANTIDAD",
        ]
        rows = [[
            123,
            "01-05-2026",
            "Cliente",
            "3000000000",
            "G123",
            "DESPACHADA",
            "ANTIOQUIA",
            "MEDELLIN",
            "Calle 1",
            "ENVIA",
            100000,
            99,
            "Producto A",
            1,
            45000,
        ]]

        records = parse_xlsx(build_xlsx(headers, rows), "ordenes_productos.xlsx")

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["id"], 123)
        self.assertEqual(records[0]["producto"], "Producto A")

    def test_rejects_ordenes_structure_without_product_columns(self):
        headers = [
            "ID",
            "FECHA",
            "NOMBRE CLIENTE",
            "TELÉFONO",
            "NÚMERO GUIA",
            "ESTATUS",
            "DEPARTAMENTO DESTINO",
            "CIUDAD DESTINO",
            "DIRECCION",
            "TRANSPORTADORA",
            "TOTAL DE LA ORDEN",
        ]
        rows = [[123, "01-05-2026", "Cliente", "3000000000", "G123", "DESPACHADA", "ANTIOQUIA", "MEDELLIN", "Calle 1", "ENVIA", 100000]]

        with self.assertRaises(InvalidDropiFileError) as ctx:
            parse_xlsx(build_xlsx(headers, rows), "ordenes.xlsx")

        self.assertIn("ordenes_productos", str(ctx.exception))
        self.assertIn("PRODUCTO", str(ctx.exception))


class MetaParserValidationTests(unittest.TestCase):
    def test_accepts_meta_campaign_report_structure(self):
        csv_text = "\n".join([
            '"Inicio del informe","Fin del informe","Nombre de la campaña",Resultados,"Indicador de resultado","Importe gastado (COP)"',
            '2026-05-04,2026-05-04,"Campaña A",3,actions:offsite_conversion.fb_pixel_purchase,39306',
        ])

        records = parse_meta_csv(csv_text.encode("utf-8"), "meta.csv")

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["fecha"], "2026-05-04")
        self.assertEqual(records[0]["campaign_name"], "Campaña A")
        self.assertEqual(records[0]["spend"], 39306)
        self.assertEqual(records[0]["results"], 3)

    def test_rejects_csv_without_meta_campaign_report_columns(self):
        csv_text = "\n".join([
            "fecha,campaign,spend",
            "2026-05-04,Campaña A,39306",
        ])

        with self.assertRaises(InvalidMetaFileError) as ctx:
            parse_meta_csv(csv_text.encode("utf-8"), "wrong.csv")

        self.assertIn("Meta Ads", str(ctx.exception))
        self.assertIn("Inicio del informe", str(ctx.exception))


class CarteraParserValidationTests(unittest.TestCase):
    def test_accepts_cartera_history_profit_movements(self):
        headers = [
            "ID",
            "FECHA",
            "TIPO",
            "MONTO",
            "MONTO PREVIO",
            "ORDEN ID",
            "NUMERO DE GUIA",
            "DESCRIPCIÓN",
        ]
        rows = [
            [
                198296498,
                "10-05-2026 00:10",
                "ENTRADA",
                49342.5,
                290611.7,
                73885291,
                "014158841780",
                "ENTRADA POR GANANCIA EN LA ORDEN COMO DROPSHIPPER: 73885291* GUIA: *014158841780*",
            ],
            [
                198689536,
                "10-05-2026 17:18",
                "ENTRADA",
                505976.0,
                9954.2,
                None,
                None,
                "ENTRADA POR RETIRO DE TARJETA DE CREDITO",
            ],
        ]

        records = parse_cartera_xlsx(build_xlsx(headers, rows), "historial.xlsx")

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["orden_id"], 73885291)
        self.assertEqual(records[0]["monto"], 49342.5)

    def test_rejects_cartera_without_required_columns(self):
        with self.assertRaises(InvalidCarteraFileError) as ctx:
            parse_cartera_xlsx(build_xlsx(["ID", "FECHA"], [[1, "10-05-2026"]]), "wrong.xlsx")

        self.assertIn("cartera", str(ctx.exception))
        self.assertIn("ORDEN ID", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
