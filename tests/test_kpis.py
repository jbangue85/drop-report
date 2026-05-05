import sqlite3
import unittest

from app.analytics import calc_kpis
from app.database import CREATE_META_ADS_SPEND, CREATE_ORDERS


class KpiTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(CREATE_ORDERS)
        self.conn.execute(CREATE_META_ADS_SPEND)

    def tearDown(self):
        self.conn.close()

    def test_return_rate_uses_real_returns_over_logistic_closures(self):
        self.conn.executemany(
            """
            INSERT INTO orders
                (id, fecha, producto, estatus, total_orden, precio_proveedor_x_cantidad, precio_flete, cantidad)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "2026-05-01", "Producto A", "ENTREGADO", 100000, 40000, 15000, 1),
                (2, "2026-05-01", "Producto A", "ENTREGADO", 100000, 40000, 15000, 1),
                (3, "2026-05-01", "Producto A", "DEVOLUCION", 100000, 40000, 15000, 1),
                (4, "2026-05-01", "Producto A", "DEVOLUCION EN BODEGA", 100000, 40000, 15000, 1),
                (5, "2026-05-01", "Producto A", "CANCELADO", 100000, 40000, 15000, 1),
            ],
        )
        self.conn.commit()

        kpis = calc_kpis(self.conn, "2026-05-01", "2026-05-01")

        self.assertEqual(kpis["entregados"], 2)
        self.assertEqual(kpis["devoluciones"], 2)
        self.assertEqual(kpis["cancelados"], 1)
        self.assertEqual(kpis["en_curso_logistico"], 0)
        self.assertEqual(kpis["tasa_entrega"], 40.0)
        self.assertEqual(kpis["tasa_devolucion"], 50.0)
        self.assertEqual(kpis["tasa_cierre_logistico"], 100.0)

    def test_confirmed_profit_uses_only_delivered_orders(self):
        self.conn.executemany(
            """
            INSERT INTO orders
                (id, fecha, producto, estatus, total_orden, ganancia, precio_proveedor_x_cantidad, precio_flete, costo_devolucion_flete, cantidad)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "2026-05-02", "Producto A", "ENTREGADO", 100000, None, 45000, 15000, 0, 1),
                (2, "2026-05-02", "Producto A", "ENTREGADO", 100000, 0, 30000, 10000, 0, 1),
                (3, "2026-05-02", "Producto A", "DEVOLUCION", 100000, 999999, 30000, 10000, 5000, 1),
                (4, "2026-05-02", "Producto A", "CANCELADO", 100000, 999999, 30000, 10000, 0, 1),
            ],
        )
        self.conn.execute(
            """
            INSERT INTO meta_ads_spend (fecha, campaign_name, spend, results)
            VALUES ('2026-05-02', 'Camp A', 5000, 0)
            """
        )
        self.conn.commit()

        kpis = calc_kpis(self.conn, "2026-05-02", "2026-05-02")

        self.assertEqual(kpis["ganancia_real"], 35000)
        self.assertEqual(kpis["ganancia_proyectada"], -10000)

    def test_projected_profit_includes_return_shipping_cost(self):
        self.conn.executemany(
            """
            INSERT INTO orders
                (id, fecha, producto, estatus, total_orden, precio_proveedor_x_cantidad, precio_flete, costo_devolucion_flete, cantidad)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "2026-05-03", "Producto A", "ENTREGADO", 100000, 0, 15000, 0, 1),
                (2, "2026-05-03", "Producto A", "DEVOLUCION", 100000, 20000, 10000, 25000, 1),
            ],
        )
        self.conn.commit()

        kpis = calc_kpis(self.conn, "2026-05-03", "2026-05-03")

        self.assertEqual(kpis["ganancia_proyectada"], 30000)

    def test_logistic_closure_excludes_cancelled_orders(self):
        self.conn.executemany(
            """
            INSERT INTO orders
                (id, fecha, producto, estatus, total_orden, precio_flete, cantidad)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "2026-05-04", "Producto A", "ENTREGADO", 100000, 15000, 1),
                (2, "2026-05-04", "Producto A", "DEVOLUCION", 100000, 15000, 1),
                (3, "2026-05-04", "Producto A", "EN REPARTO", 100000, 15000, 1),
                (4, "2026-05-04", "Producto A", "CANCELADO", 100000, 15000, 1),
            ],
        )
        self.conn.commit()

        kpis = calc_kpis(self.conn, "2026-05-04", "2026-05-04")

        self.assertEqual(kpis["en_curso_logistico"], 1)
        self.assertEqual(kpis["tasa_cierre_logistico"], 66.7)


if __name__ == "__main__":
    unittest.main()
