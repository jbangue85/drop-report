import sqlite3
import unittest

from app.analytics import calc_kpis, get_action_orders
from app.database import CREATE_CALL_NOTES, CREATE_META_ADS_SPEND, CREATE_ORDERS


class ActionOrdersTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(CREATE_ORDERS)
        self.conn.execute(CREATE_CALL_NOTES)
        self.conn.execute(CREATE_META_ADS_SPEND)

    def tearDown(self):
        self.conn.close()

    def test_includes_orders_stale_for_more_than_48_business_hours(self):
        self.conn.execute(
            """
            INSERT INTO orders
                (id, fecha, hora, estatus, fecha_ultimo_movimiento, hora_ultimo_movimiento, nombre_cliente, direccion)
            VALUES (1, '2026-05-01', '08:00:00', 'DESPACHADA', '2026-05-01', '08:00:00', 'Cliente A', 'Calle 1 # 2-3')
            """
        )
        self.conn.commit()

        rows = get_action_orders(self.conn, reference_now="2026-05-05 09:00:00")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], 1)
        self.assertEqual(rows[0]["sin_movimiento_48h"], 1)
        self.assertEqual(rows[0]["pendiente_recibir_oficina"], 0)
        self.assertEqual(rows[0]["requiere_llamada"], 0)
        self.assertEqual(rows[0]["tipo_gestion"], "soporte")
        self.assertEqual(rows[0]["direccion"], "Calle 1 # 2-3")

    def test_weekend_hours_do_not_count_as_stale_movement_time(self):
        self.conn.execute(
            """
            INSERT INTO orders
                (id, fecha, hora, estatus, fecha_ultimo_movimiento, hora_ultimo_movimiento, nombre_cliente)
            VALUES (6, '2026-05-01', '18:00:00', 'DESPACHADA', '2026-05-01', '18:00:00', 'Cliente F')
            """
        )
        self.conn.commit()

        rows = get_action_orders(self.conn, reference_now="2026-05-04 10:00:00")

        self.assertEqual(rows, [])

    def test_includes_orders_pending_office_receipt(self):
        self.conn.execute(
            """
            INSERT INTO orders
                (id, fecha, hora, estatus, novedad, nombre_cliente)
            VALUES (2, '2026-05-02', '10:00:00', 'EN REPARTO', 'COORDINAR LA ENTREGA EN OFICINA', 'Cliente B')
            """
        )
        self.conn.commit()

        rows = get_action_orders(self.conn, reference_now="2026-05-02 12:00:00")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], 2)
        self.assertEqual(rows[0]["pendiente_recibir_oficina"], 1)
        self.assertEqual(rows[0]["sin_movimiento_48h"], 0)
        self.assertEqual(rows[0]["requiere_llamada"], 1)
        self.assertEqual(rows[0]["tipo_gestion"], "llamada")

    def test_includes_orders_with_reclamar_en_oficina_phrase(self):
        self.conn.execute(
            """
            INSERT INTO orders
                (id, fecha, hora, estatus, concepto_ultimo_movimiento, nombre_cliente)
            VALUES (3, '2026-05-02', '10:00:00', 'EN REPARTO', 'RECLAMAR EN OFICINA', 'Cliente C')
            """
        )
        self.conn.commit()

        rows = get_action_orders(self.conn, reference_now="2026-05-02 12:00:00")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], 3)
        self.assertEqual(rows[0]["pendiente_recibir_oficina"], 1)

    def test_support_management_does_not_count_as_call_attempt(self):
        self.conn.execute(
            """
            INSERT INTO orders
                (id, fecha, hora, estatus, fecha_ultimo_movimiento, hora_ultimo_movimiento, nombre_cliente)
            VALUES (5, '2026-05-01', '08:00:00', 'DESPACHADA', '2026-05-01', '08:00:00', 'Cliente D')
            """
        )
        self.conn.execute(
            """
            INSERT INTO call_notes (order_id, agent, resultado, notas)
            VALUES (5, 'admin', 'SOPORTE_DROPI', 'Caso montado en soporte')
            """
        )
        self.conn.commit()

        rows = get_action_orders(self.conn, reference_now="2026-05-05 09:00:00")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ultima_gestion"], "SOPORTE_DROPI")
        self.assertEqual(rows[0]["intentos"], 0)
        self.assertEqual(rows[0]["requiere_llamada"], 0)

    def test_kpis_count_combined_action_rules_without_double_counting(self):
        self.conn.executemany(
            """
            INSERT INTO orders
                (id, fecha, hora, estatus, fecha_ultimo_movimiento, hora_ultimo_movimiento, novedad)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "2026-05-01", "08:00:00", "PENDIENTE CONFIRMACION", None, None, None),
                (2, "2026-05-01", "08:00:00", "DESPACHADA", "2026-05-01", "08:00:00", None),
                (3, "2026-05-01", "08:00:00", "EN REPARTO", "2026-05-02", "11:30:00", "COORDINAR LA ENTREGA EN OFICINA"),
                (4, "2026-05-01", "08:00:00", "ENTREGADO", "2026-05-01", "08:00:00", None),
            ],
        )
        self.conn.commit()

        kpis = calc_kpis(
            self.conn,
            "2026-05-01",
            "2026-05-01",
            reference_now="2026-05-05 12:00:00",
        )

        self.assertEqual(kpis["requieren_accion"], 3)


if __name__ == "__main__":
    unittest.main()
