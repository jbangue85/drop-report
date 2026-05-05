import sqlite3
import unittest

from app.analytics import calc_daily_control
from app.database import (
    CREATE_CAMPAIGN_MAP,
    CREATE_META_ADS_SPEND,
    CREATE_ORDERS,
    CREATE_PRODUCT_PROJECTION_CONFIG,
)


class DailyControlProjectionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(CREATE_ORDERS)
        self.conn.execute(CREATE_META_ADS_SPEND)
        self.conn.execute(CREATE_CAMPAIGN_MAP)
        self.conn.execute(CREATE_PRODUCT_PROJECTION_CONFIG)

    def tearDown(self):
        self.conn.close()

    def test_projected_control_uses_excel_style_formula(self):
        self.conn.execute(
            """
            INSERT INTO product_projection_config
                (producto, pct_devolucion, flete_base_dev, precio_venta, costo_proveedor)
            VALUES ('Producto A', 0.25, 21656, 109900, 43500)
            """
        )
        self.conn.executemany(
            """
            INSERT INTO orders
                (id, fecha, producto, estatus, total_orden, precio_proveedor_x_cantidad, precio_flete, cantidad)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "2026-04-15", "Producto A", "ENTREGADO", 109900, 43500, 21656, 1),
                (2, "2026-04-15", "Producto A", "ENTREGADO", 109900, 43500, 21656, 1),
                (3, "2026-04-15", "Producto A", "ENTREGADO", 109900, 43500, 21656, 1),
                (4, "2026-04-15", "Producto A", "ENTREGADO", 109900, 43500, 21656, 1),
                (5, "2026-04-15", "Producto A", "CANCELADO", 109900, 43500, 21656, 1),
                (6, "2026-04-15", "Producto A", "ENTREGADO", 109900, 43500, 21656, 1),
            ],
        )
        self.conn.execute(
            "INSERT INTO campaign_map (campaign_name, producto) VALUES ('Camp A', 'Producto A')"
        )
        self.conn.execute(
            """
            INSERT INTO meta_ads_spend (fecha, campaign_name, spend, results)
            VALUES ('2026-04-15', 'Camp A', 70773, 0)
            """
        )
        self.conn.commit()

        rows = calc_daily_control(self.conn, "2026-04-15", "2026-04-15")
        self.assertEqual(len(rows), 1)
        row = rows[0]

        self.assertEqual(row["ventas_dia"], 6)
        self.assertEqual(row["ventas_canceladas"], 1)
        self.assertAlmostEqual(row["pct_cancelado"], 1 / 6, places=5)
        self.assertAlmostEqual(row["pct_devolucion"], 0.25, places=5)
        self.assertAlmostEqual(row["ventas_efectivas"], 3.5, places=5)
        self.assertAlmostEqual(row["cpa"], 70773 / 3.5, places=5)
        self.assertAlmostEqual(row["utilidad_total"], 60565.66667, places=2)
        self.assertAlmostEqual(row["roi"], 60565.66667 / 70773, places=5)

    def test_zero_effective_sales_avoids_division_errors(self):
        self.conn.execute(
            """
            INSERT INTO product_projection_config
                (producto, pct_devolucion, flete_base_dev, precio_venta, costo_proveedor)
            VALUES ('Producto B', 0.25, 21656, 109900, 43500)
            """
        )
        self.conn.execute(
            """
            INSERT INTO orders
                (id, fecha, producto, estatus, total_orden, precio_proveedor_x_cantidad, precio_flete, cantidad)
            VALUES (1, '2026-04-22', 'Producto B', 'CANCELADO', 109900, 43500, 21656, 1)
            """
        )
        self.conn.commit()

        row = calc_daily_control(self.conn, "2026-04-22", "2026-04-22")[0]
        self.assertEqual(row["cpa"], 0)
        self.assertEqual(row["roi"], 0)
        self.assertAlmostEqual(row["ventas_efectivas"], -0.25, places=5)

    def test_product_without_manual_config_uses_fallback_from_orders(self):
        self.conn.execute(
            """
            INSERT INTO orders
                (id, fecha, producto, estatus, total_orden, precio_proveedor_x_cantidad, precio_flete, cantidad)
            VALUES (1, '2026-04-18', 'Producto C', 'ENTREGADO', 120000, 50000, 20000, 1)
            """
        )
        self.conn.execute(
            "INSERT INTO campaign_map (campaign_name, producto) VALUES ('Camp C', 'Producto C')"
        )
        self.conn.execute(
            """
            INSERT INTO meta_ads_spend (fecha, campaign_name, spend, results)
            VALUES ('2026-04-18', 'Camp C', 10000, 0)
            """
        )
        self.conn.commit()

        row = calc_daily_control(self.conn, "2026-04-18", "2026-04-18")[0]
        self.assertAlmostEqual(row["pct_devolucion"], 0.25, places=5)
        self.assertEqual(row["precio_venta"], 120000)
        self.assertEqual(row["costo_proveedor"], 50000)
        self.assertEqual(row["flete_base_dev"], 20000)
        self.assertGreater(row["utilidad_total"], 0)

    def test_spend_without_orders_still_returns_projection_row(self):
        self.conn.execute(
            """
            INSERT INTO product_projection_config
                (producto, pct_devolucion, flete_base_dev, precio_venta, costo_proveedor)
            VALUES ('Producto D', 0.2, 15000, 80000, 30000)
            """
        )
        self.conn.execute(
            "INSERT INTO campaign_map (campaign_name, producto) VALUES ('Camp D', 'Producto D')"
        )
        self.conn.execute(
            """
            INSERT INTO meta_ads_spend (fecha, campaign_name, spend, results)
            VALUES ('2026-04-20', 'Camp D', 12000, 0)
            """
        )
        self.conn.commit()

        row = calc_daily_control(self.conn, "2026-04-20", "2026-04-20")[0]
        self.assertEqual(row["ventas_dia"], 0)
        self.assertEqual(row["ad_spend"], 12000)
        self.assertEqual(row["utilidad_total"], -12000)
        self.assertEqual(row["roi"], -1)


if __name__ == "__main__":
    unittest.main()
