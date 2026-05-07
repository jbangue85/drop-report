CREATE TABLE IF NOT EXISTS attention_rules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key       TEXT NOT NULL UNIQUE,
    category       TEXT NOT NULL,
    label          TEXT NOT NULL,
    match_scope    TEXT NOT NULL DEFAULT 'any',
    match_text     TEXT NOT NULL,
    transportadora TEXT,
    severity       TEXT NOT NULL DEFAULT 'medium',
    requires_call  INTEGER NOT NULL DEFAULT 1,
    guidance       TEXT,
    active         INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_attention_rules_active
ON attention_rules(active, requires_call, category);

INSERT OR IGNORE INTO attention_rules
    (rule_key, category, label, match_scope, match_text, severity, guidance)
VALUES
    ('office_reclamar_en_oficina', 'office_pickup', 'Reclamar en oficina', 'any', 'RECLAMAR EN OFICINA', 'high', 'Contactar al cliente y confirmar nombre, cedula, oficina y fecha de reclamo.'),
    ('office_bodega_receptoria', 'office_pickup', 'Entregar en bodega receptoria', 'any', 'BODEGA RECEPTORIA', 'high', 'Validar si el cliente reclamara en oficina o si prefiere nuevo ofrecimiento a direccion.'),
    ('office_bodega_receptoria_accent', 'office_pickup', 'Entregar en bodega receptoria', 'any', 'BODEGA RECEPTORÍA', 'high', 'Validar si el cliente reclamara en oficina o si prefiere nuevo ofrecimiento a direccion.'),
    ('office_punto_drop', 'office_pickup', 'En punto Drop', 'any', 'PUNTO DROP', 'high', 'Confirmar con el cliente que pasara a recoger el paquete.'),
    ('office_pls_tcc', 'office_pickup', 'Reclamo en PLS TCC', 'any', 'PLS TCC', 'high', 'Confirmar datos del destinatario, PLS principal y fecha de reclamo.'),
    ('office_centro_operacion', 'office_pickup', 'Centro de operacion', 'any', 'CENTRO DE OPERACION', 'high', 'Confirmar punto de reclamo y fecha de visita del cliente.'),
    ('office_centro_operacion_accent', 'office_pickup', 'Centro de operacion', 'any', 'CENTRO DE OPERACIÓN', 'high', 'Confirmar punto de reclamo y fecha de visita del cliente.'),
    ('office_no_reclama', 'office_pickup', 'No reclama mercancia en oficina', 'any', 'NO RECLAMA MERCANCIA', 'high', 'Recordar al cliente que debe reclamar; si ya no desea, definir devolucion o nuevo ofrecimiento.'),
    ('office_no_reclama_accent', 'office_pickup', 'No reclama mercancia en oficina', 'any', 'NO RECLAMA MERCANCÍA', 'high', 'Recordar al cliente que debe reclamar; si ya no desea, definir devolucion o nuevo ofrecimiento.'),
    ('office_coordinar_entrega', 'office_pickup', 'Coordinar entrega', 'any', 'COORDINAR LA ENTREGA', 'high', 'Contactar al cliente y confirmar disponibilidad, direccion u oficina de reclamo.'),
    ('office_no_hay_quien_reciba', 'delivery_attempt', 'No hay quien reciba', 'any', 'NO HAY QUIEN RECIBA', 'high', 'Confirmar con el cliente una persona disponible para recibir y jornada.'),

    ('address_direccion_errada', 'address_issue', 'Direccion errada', 'any', 'DIRECCION ERRADA', 'high', 'Confirmar direccion completa, barrio, ciudad y punto de referencia.'),
    ('address_direccion_errada_accent', 'address_issue', 'Direccion errada', 'any', 'DIRECCIÓN ERRADA', 'high', 'Confirmar direccion completa, barrio, ciudad y punto de referencia.'),
    ('address_direccion_incorrecta', 'address_issue', 'Direccion incorrecta', 'any', 'DIRECCION INCORRECTA', 'high', 'Confirmar direccion completa, barrio, ciudad y punto de referencia.'),
    ('address_direccion_incorrecta_accent', 'address_issue', 'Direccion incorrecta', 'any', 'DIRECCIÓN INCORRECTA', 'high', 'Confirmar direccion completa, barrio, ciudad y punto de referencia.'),
    ('address_direccion_incompleta', 'address_issue', 'Direccion incompleta', 'any', 'DIRECCION INCOMPLETA', 'high', 'Solicitar datos faltantes de direccion, barrio y referencias.'),
    ('address_direccion_incompleta_accent', 'address_issue', 'Direccion incompleta', 'any', 'DIRECCIÓN INCOMPLETA', 'high', 'Solicitar datos faltantes de direccion, barrio y referencias.'),
    ('address_domicilio_incorrecto', 'address_issue', 'Domicilio incorrecto', 'any', 'DOMICILIO INCORRECTO', 'high', 'Confirmar ciudad, direccion, barrio y punto de referencia.'),
    ('address_no_existe', 'address_issue', 'Direccion no existe', 'any', 'DIRECCION DESTINATARIO NO EXISTE', 'high', 'Validar ciudad y direccion completa con el cliente.'),
    ('address_no_conocen', 'address_issue', 'No conocen destinatario', 'any', 'NO CONOCEN DESTINATARIO', 'high', 'Validar destinatario, persona que recibe y direccion completa.'),
    ('address_nomenclatura', 'address_issue', 'Nomenclatura no coincide', 'any', 'NOMENCLATURA NO COINCIDE', 'high', 'Confirmar nomenclatura, barrio y referencias.'),

    ('customer_ausente', 'delivery_attempt', 'Cliente ausente', 'any', 'CLIENTE AUSENTE', 'medium', 'Validar disponibilidad si se repite o si ya hubo varios intentos.'),
    ('customer_no_localizable', 'no_contact', 'Cliente no localizable', 'any', 'CLIENTE NO LOCALIZABLE', 'high', 'Intentar contacto para confirmar datos y voluntad de recibir.'),
    ('customer_no_disponible', 'delivery_attempt', 'Cliente no disponible', 'any', 'CLIENTE NO DISPONIBLE', 'high', 'Confirmar fecha y jornada de entrega.'),
    ('customer_cerrado', 'delivery_attempt', 'Cerrado o nadie recibe', 'any', 'CERRADO', 'high', 'Confirmar disponibilidad de quien recibe y jornada.'),
    ('customer_visita_no_entrega', 'delivery_attempt', 'Visita sin entrega', 'any', 'SE VISITA, NO SE LOGRA ENTREGA', 'high', 'Confirmar fecha y jornada para nuevo ofrecimiento.'),
    ('customer_intentados_no_entregados', 'delivery_attempt', 'Intentos no entregados', 'any', 'INTENTADOS NO ENTREGADOS', 'high', 'Contactar antes de autorizar otro intento.'),

    ('refusal_rechaza_paquete', 'refusal', 'Rechaza paquete', 'any', 'RECHAZA PAQUETE', 'high', 'Validar si el cliente aun desea el producto antes de volver a ofrecer.'),
    ('refusal_niega_recibir', 'refusal', 'Cliente se niega a recibir', 'any', 'NIEGA A RECIBIR', 'high', 'Validar voluntad de recibir y dinero disponible; si no, solicitar devolucion.'),
    ('refusal_rehusa_recibir', 'refusal', 'Destinatario rehusa recibir', 'any', 'REHUSA A RECIBIR', 'high', 'Confirmar si desea el producto o si se debe devolver.'),
    ('refusal_cancela_entrega', 'refusal', 'Cliente cancela entrega', 'any', 'CLIENTE CANCELA', 'high', 'Confirmar cancelacion real o recuperar entrega.'),

    ('payment_no_dinero', 'payment_issue', 'No tiene dinero', 'any', 'NO TIENE EL DINERO', 'high', 'Confirmar fecha de pago y recomendar efectivo disponible.'),
    ('payment_sin_pago', 'payment_issue', 'Sin pago en entrega', 'any', 'SIN PAGO EN ENTREGA', 'high', 'Confirmar monto y disponibilidad para pago contra entrega.'),
    ('payment_no_pago', 'payment_issue', 'No pago en entrega', 'any', 'NO PAGO EN ENTREGA', 'high', 'Confirmar monto y disponibilidad para pago contra entrega.'),

    ('coverage_zona_alto_riesgo', 'coverage_issue', 'Zona de alto riesgo', 'any', 'ZONA DE ALTO RIESGO', 'high', 'Solicitar direccion alterna urbana u oficina de reclamo.'),
    ('coverage_no_cubre', 'coverage_issue', 'Zona sin cobertura', 'any', 'NO SE CUBRE', 'high', 'Solicitar direccion alterna urbana u oficina de reclamo.'),
    ('coverage_sector_no_cubre', 'coverage_issue', 'Sector no cubierto', 'any', 'SECTOR DE LA POBLACION', 'high', 'Solicitar direccion alterna urbana u oficina de reclamo.'),
    ('coverage_sector_no_cubre_accent', 'coverage_issue', 'Sector no cubierto', 'any', 'SECTOR DE LA POBLACIÓN', 'high', 'Solicitar direccion alterna urbana u oficina de reclamo.');
