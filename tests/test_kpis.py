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
        self.assertEqual(kpis["tasa_entrega"], 40.0)
        self.assertEqual(kpis["tasa_devolucion"], 50.0)


if __name__ == "__main__":
    unittest.main()
