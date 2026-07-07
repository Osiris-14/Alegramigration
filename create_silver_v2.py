"""
SILVER SCHEMA v2 - Schema completo mejorado
17 tablas: 4 mejoradas + 7 transaccionales nuevas + 6 catálogos
"""

import os
import psycopg2
from datetime import datetime

CONN_STRING = os.environ.get("SUPABASE_DB_URL")
if not CONN_STRING:
    raise ValueError("Falta variable de entorno SUPABASE_DB_URL")


def run(cur, sql):
    cur.execute(sql)


def count(cur, table):
    cur.execute(f"SELECT count(*) FROM silver.{table}")
    return cur.fetchone()[0]


def main():
    print("Conectando a Supabase...")
    conn = psycopg2.connect(CONN_STRING)
    conn.autocommit = False
    cur = conn.cursor()
    print("Conexion exitosa\n")

    # ============================================================
    # TABLAS MEJORADAS (DROP + RECREATE)
    # ============================================================

    print("=" * 60)
    print("BLOQUE 1: TABLAS EXISTENTES MEJORADAS")
    print("=" * 60)

    # ----------------------------------------------------------
    # silver.contactos - MEJORADO
    # ----------------------------------------------------------
    print("\n[1.1] silver.contactos (mejorado)...")
    run(cur, "CREATE SCHEMA IF NOT EXISTS silver;")
    run(cur, "DROP TABLE IF EXISTS silver.contactos CASCADE;")
    run(cur, """
    CREATE TABLE silver.contactos AS
    SELECT
        c.id                                                        AS alegra_id,
        trim(c.nombre)                                              AS nombre,
        -- RNc / identificacion
        CASE
            WHEN trim(c.identificacion->>'number') IS NOT NULL
             AND trim(c.identificacion->>'number') != ''
            THEN trim(c.identificacion->>'number')
            ELSE '0000000'
        END                                                         AS rnc,
        c.identificacion->>'type'                                   AS tipo_identificacion,
        -- Tipo cliente/proveedor desde array JSON
        c.tipo::text ILIKE '%client%'                               AS es_cliente,
        c.tipo::text ILIKE '%provider%'                             AS es_proveedor,
        -- Contacto
        c.correo                                                    AS email,
        CASE
            WHEN regexp_replace(COALESCE(c.telefono_principal, c.celular, ''), '[^0-9]', '', 'g') = ''
                THEN NULL
            WHEN length(regexp_replace(COALESCE(c.telefono_principal, c.celular, ''), '[^0-9]', '', 'g')) = 11
             AND left(regexp_replace(COALESCE(c.telefono_principal, c.celular, ''), '[^0-9]', '', 'g'), 1) = '1'
                THEN substring(regexp_replace(COALESCE(c.telefono_principal, c.celular, ''), '[^0-9]', '', 'g') FROM 2)
            WHEN length(regexp_replace(COALESCE(c.telefono_principal, c.celular, ''), '[^0-9]', '', 'g')) = 10
                THEN regexp_replace(COALESCE(c.telefono_principal, c.celular, ''), '[^0-9]', '', 'g')
            ELSE NULL
        END                                                         AS telefono,
        -- Dirección aplanada desde JSON
        nullif(trim(c.direccion->>'description'), '')               AS dir_descripcion,
        nullif(trim(c.direccion->>'municipality'), '')              AS dir_municipio,
        nullif(trim(c.direccion->>'province'), '')                  AS dir_provincia,
        nullif(trim(c.direccion->>'country'), '')                   AS dir_pais,
        -- Campos comerciales
        c.limite_credito,
        c.lista_precio_id,
        c.vendedor_id,
        c.termino_pago_id,
        -- IDs / fechas
        c.uuid,
        c.fecha_creacion,
        c.fecha_actualizacion,
        c.estado,
        c.sincronizado_en                                           AS alegra_sync_at
    FROM alegra.contactos c;
    """)
    run(cur, "ALTER TABLE silver.contactos ADD PRIMARY KEY (alegra_id);")
    run(cur, "CREATE INDEX ON silver.contactos(rnc);")
    run(cur, "CREATE INDEX ON silver.contactos(es_cliente);")
    run(cur, "CREATE INDEX ON silver.contactos(es_proveedor);")
    run(cur, "CREATE INDEX ON silver.contactos(vendedor_id);")
    run(cur, "CREATE INDEX ON silver.contactos(estado);")
    conn.commit()
    print(f"  OK - {count(cur, 'contactos'):,} filas")

    # ----------------------------------------------------------
    # silver.productos - MEJORADO
    # ----------------------------------------------------------
    print("\n[1.2] silver.productos (mejorado)...")
    run(cur, "DROP TABLE IF EXISTS silver.productos CASCADE;")
    run(cur, """
    CREATE TABLE silver.productos AS
    WITH pm AS (
        SELECT id,
            (SELECT (elem->>'price')::numeric
             FROM jsonb_array_elements(precio) elem
             WHERE (elem->>'main')::boolean = true LIMIT 1)  AS precio_1,
            (SELECT (elem->>'price')::numeric
             FROM jsonb_array_elements(precio) elem
             WHERE (elem->>'main')::boolean = false LIMIT 1) AS precio_2
        FROM alegra.productos
        WHERE precio IS NOT NULL AND jsonb_typeof(precio) = 'array'
    ),
    it AS (
        SELECT id,
            EXISTS (
                SELECT 1 FROM jsonb_array_elements(impuestos) imp
                WHERE imp->>'type' = 'ITBIS'
            ) AS tiene_itbis
        FROM alegra.productos
        WHERE impuestos IS NOT NULL AND jsonb_typeof(impuestos) = 'array'
    )
    SELECT
        p.id                                                        AS alegra_id,
        left(trim(p.nombre), 80)                                    AS nombre,
        p.descripcion,
        p.tipo,
        p.tipo_item,
        p.estado,
        CASE
            WHEN p.referencia IS NOT NULL AND p.referencia::text != 'null'
            THEN nullif(trim(p.referencia->>'reference'), '')
            ELSE NULL
        END                                                         AS referencia,
        COALESCE(pm.precio_1, 0)                                    AS precio_1,
        pm.precio_2,
        COALESCE((p.inventario->>'unitCost')::numeric, 0)           AS costo,
        (p.inventario->>'availableQuantity')::numeric               AS stock_disponible,
        nullif(trim(p.inventario->>'unit'), '')                     AS unidad,
        COALESCE(it.tiene_itbis, false)                             AS tiene_itbis,
        p.impuestos                                                  AS impuestos_raw,
        p.subitems,
        p.categoria_id,
        p.sincronizado_en                                           AS alegra_sync_at
    FROM alegra.productos p
    LEFT JOIN pm ON pm.id = p.id
    LEFT JOIN it ON it.id = p.id;
    """)
    run(cur, "ALTER TABLE silver.productos ADD PRIMARY KEY (alegra_id);")
    run(cur, "CREATE INDEX ON silver.productos(estado);")
    run(cur, "CREATE INDEX ON silver.productos(tipo);")
    run(cur, "CREATE INDEX ON silver.productos(categoria_id);")
    run(cur, "CREATE INDEX ON silver.productos(tiene_itbis);")
    conn.commit()
    print(f"  OK - {count(cur, 'productos'):,} filas")

    # ----------------------------------------------------------
    # silver.facturas_venta - MEJORADO
    # ----------------------------------------------------------
    print("\n[1.3] silver.facturas_venta (mejorado)...")
    run(cur, "DROP TABLE IF EXISTS silver.facturas_venta CASCADE;")
    run(cur, """
    CREATE TABLE silver.facturas_venta AS
    SELECT
        f.id                                                        AS alegra_id,
        f.numero                                                    AS ncf,
        f.cliente_id::text                                          AS cliente_alegra_id,
        f.vendedor_id::text                                         AS vendedor_alegra_id,
        f.fecha,
        f.fecha_vencimiento,
        f.estado,
        f.subtotal,
        f.subtotal_con_descuento,
        CASE
            WHEN f.descuento IS NOT NULL AND f.descuento::text ~ '^[0-9]+(\.[0-9]+)?$'
            THEN f.descuento::text::numeric
            ELSE NULL
        END                                                         AS descuento_monto,
        CASE
            WHEN f.impuesto IS NOT NULL AND f.impuesto::text ~ '^[0-9]+(\.[0-9]+)?$'
            THEN f.impuesto::text::numeric
            ELSE NULL
        END                                                         AS impuesto_monto,
        f.total,
        f.total_pagado,
        f.saldo,
        f.metodo_pago,
        f.tipo_pago,
        f.tipo_ingreso,
        f.bodega_id,
        f.centro_costo_id,
        f.lista_precio_id,
        f.termino_pago_id,
        f.plantilla_numeracion_id,
        f.observaciones,
        -- Items de la factura como JSONB para análisis posterior
        f.items,
        -- Cantidad de ítems calculada
        CASE
            WHEN f.items IS NOT NULL AND jsonb_typeof(f.items) = 'array'
            THEN jsonb_array_length(f.items)
            ELSE 0
        END                                                         AS num_items,
        f.pagos_aplicados,
        f.sincronizado_en                                           AS alegra_sync_at
    FROM alegra.facturas_venta f;
    """)
    run(cur, "ALTER TABLE silver.facturas_venta ADD PRIMARY KEY (alegra_id);")
    run(cur, "CREATE INDEX ON silver.facturas_venta(cliente_alegra_id);")
    run(cur, "CREATE INDEX ON silver.facturas_venta(vendedor_alegra_id);")
    run(cur, "CREATE INDEX ON silver.facturas_venta(fecha);")
    run(cur, "CREATE INDEX ON silver.facturas_venta(estado);")
    run(cur, "CREATE INDEX ON silver.facturas_venta(ncf);")
    run(cur, "CREATE INDEX ON silver.facturas_venta(bodega_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'facturas_venta'):,} filas")

    # ----------------------------------------------------------
    # silver.usuarios - MEJORADO
    # ----------------------------------------------------------
    print("\n[1.4] silver.usuarios (mejorado)...")
    run(cur, "DROP TABLE IF EXISTS silver.usuarios CASCADE;")
    run(cur, """
    CREATE TABLE silver.usuarios AS
    SELECT
        u.id                                                        AS alegra_id,
        trim(u.nombre)                                              AS nombre,
        trim(u.apellido)                                            AS apellido,
        trim(concat_ws(' ',
            nullif(trim(u.nombre), ''),
            nullif(trim(u.apellido), '')
        ))                                                          AS nombre_completo,
        u.correo                                                    AS email,
        u.nombre_usuario,
        -- rol puede ser texto o JSONB según el registro
        CASE
            WHEN u.rol IS NULL THEN NULL
            WHEN jsonb_typeof(u.rol::jsonb) = 'object' THEN u.rol::jsonb->>'name'
            ELSE u.rol::text
        END                                                         AS rol,
        u.cargo,
        CASE
            WHEN nullif(trim(u.telefono), '') IS NULL THEN NULL
            WHEN regexp_replace(trim(u.telefono), '[^0-9]', '', 'g') = '' THEN NULL
            ELSE regexp_replace(trim(u.telefono), '[^0-9]', '', 'g')
        END                                                         AS telefono,
        nullif(trim(u.codigo_telefono), '')                        AS codigo_telefono,
        u.idioma,
        u.estado,
        u.sincronizado_en                                           AS alegra_sync_at
    FROM alegra.usuarios u;
    """)
    run(cur, "ALTER TABLE silver.usuarios ADD PRIMARY KEY (alegra_id);")
    run(cur, "CREATE INDEX ON silver.usuarios(estado);")
    conn.commit()
    print(f"  OK - {count(cur, 'usuarios'):,} filas")

    # ============================================================
    # TABLAS NUEVAS - TRANSACCIONALES
    # ============================================================

    print("\n" + "=" * 60)
    print("BLOQUE 2: TABLAS TRANSACCIONALES NUEVAS")
    print("=" * 60)

    # ----------------------------------------------------------
    # silver.cotizaciones - NUEVA
    # ----------------------------------------------------------
    print("\n[2.1] silver.cotizaciones (NUEVA)...")
    run(cur, "DROP TABLE IF EXISTS silver.cotizaciones CASCADE;")
    run(cur, """
    CREATE TABLE silver.cotizaciones AS
    SELECT
        q.id                                                        AS alegra_id,
        q.numero,
        q.cliente_id::text                                          AS cliente_alegra_id,
        q.vendedor_id::text                                         AS vendedor_alegra_id,
        q.fecha,
        q.fecha_vencimiento,
        q.estado,
        -- Moneda aplanada
        q.moneda->>'code'                                           AS moneda_codigo,
        q.moneda->>'symbol'                                         AS moneda_simbolo,
        COALESCE((q.moneda->>'exchangeRate')::numeric, 1)           AS tasa_cambio,
        q.total,
        q.bodega_id,
        q.centro_costo_id,
        q.lista_precio_id,
        q.plantilla_numeracion_id,
        q.observaciones,
        -- Items como JSONB
        q.items,
        CASE
            WHEN q.items IS NOT NULL AND jsonb_typeof(q.items) = 'array'
            THEN jsonb_array_length(q.items)
            ELSE 0
        END                                                         AS num_items,
        q.sincronizado_en                                           AS alegra_sync_at
    FROM alegra.cotizaciones q;
    """)
    run(cur, "ALTER TABLE silver.cotizaciones ADD PRIMARY KEY (alegra_id);")
    run(cur, "CREATE INDEX ON silver.cotizaciones(cliente_alegra_id);")
    run(cur, "CREATE INDEX ON silver.cotizaciones(vendedor_alegra_id);")
    run(cur, "CREATE INDEX ON silver.cotizaciones(fecha);")
    run(cur, "CREATE INDEX ON silver.cotizaciones(estado);")
    run(cur, "CREATE INDEX ON silver.cotizaciones(numero);")
    conn.commit()
    print(f"  OK - {count(cur, 'cotizaciones'):,} filas")

    # ----------------------------------------------------------
    # silver.pagos - NUEVA
    # ----------------------------------------------------------
    print("\n[2.2] silver.pagos (NUEVA)...")
    run(cur, "DROP TABLE IF EXISTS silver.pagos CASCADE;")
    run(cur, """
    CREATE TABLE silver.pagos AS
    SELECT
        p.id                                                        AS alegra_id,
        p.numero,
        p.tipo,            -- 'in' = cobro, 'out' = pago a proveedor
        p.fecha,
        p.monto,
        p.estado,
        p.metodo_pago,
        p.cliente_id::text                                          AS contacto_alegra_id,
        p.cuenta_bancaria_id,
        p.centro_costo_id,
        p.plantilla_numeracion_id,
        p.observaciones,
        -- Facturas aplicadas como JSONB
        p.facturas_compra_aplicadas                                 AS facturas_aplicadas,
        p.sincronizado_en                                           AS alegra_sync_at
    FROM alegra.pagos p;
    """)
    run(cur, "ALTER TABLE silver.pagos ADD PRIMARY KEY (alegra_id);")
    run(cur, "CREATE INDEX ON silver.pagos(contacto_alegra_id);")
    run(cur, "CREATE INDEX ON silver.pagos(fecha);")
    run(cur, "CREATE INDEX ON silver.pagos(tipo);")
    run(cur, "CREATE INDEX ON silver.pagos(estado);")
    run(cur, "CREATE INDEX ON silver.pagos(metodo_pago);")
    run(cur, "CREATE INDEX ON silver.pagos(cuenta_bancaria_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'pagos'):,} filas")

    # ----------------------------------------------------------
    # silver.facturas_compra - NUEVA
    # ----------------------------------------------------------
    print("\n[2.3] silver.facturas_compra (NUEVA)...")
    run(cur, "DROP TABLE IF EXISTS silver.facturas_compra CASCADE;")
    run(cur, """
    CREATE TABLE silver.facturas_compra AS
    SELECT
        fc.id                                                       AS alegra_id,
        fc.proveedor_id::text                                       AS proveedor_alegra_id,
        fc.fecha,
        fc.fecha_vencimiento,
        fc.estado,
        fc.total,
        fc.total_pagado,
        fc.saldo,
        fc.bodega_id,
        fc.centro_costo_id,
        fc.sujeta_proporcionalidad,
        fc.observaciones,
        fc.compras,
        -- Cantidad de ítems
        CASE
            WHEN fc.compras IS NOT NULL AND jsonb_typeof(fc.compras) = 'array'
            THEN jsonb_array_length(fc.compras)
            ELSE 0
        END                                                         AS num_items,
        fc.retenciones,
        fc.pagos_aplicados,
        fc.sincronizado_en                                          AS alegra_sync_at
    FROM alegra.facturas_compra fc;
    """)
    run(cur, "ALTER TABLE silver.facturas_compra ADD PRIMARY KEY (alegra_id);")
    run(cur, "CREATE INDEX ON silver.facturas_compra(proveedor_alegra_id);")
    run(cur, "CREATE INDEX ON silver.facturas_compra(fecha);")
    run(cur, "CREATE INDEX ON silver.facturas_compra(estado);")
    run(cur, "CREATE INDEX ON silver.facturas_compra(saldo);")
    conn.commit()
    print(f"  OK - {count(cur, 'facturas_compra'):,} filas")

    # ----------------------------------------------------------
    # silver.ordenes_compra - NUEVA
    # ----------------------------------------------------------
    print("\n[2.4] silver.ordenes_compra (NUEVA)...")
    run(cur, "DROP TABLE IF EXISTS silver.ordenes_compra CASCADE;")
    run(cur, """
    CREATE TABLE silver.ordenes_compra AS
    SELECT
        oc.id                                                       AS alegra_id,
        oc.proveedor_id::text                                       AS proveedor_alegra_id,
        oc.fecha,
        oc.fecha_entrega,
        oc.estado,
        oc.subtotal,
        oc.total,
        oc.bodega_id,
        oc.centro_costo_id,
        oc.observaciones,
        oc.compras,
        CASE
            WHEN oc.compras IS NOT NULL AND jsonb_typeof(oc.compras) = 'array'
            THEN jsonb_array_length(oc.compras)
            ELSE 0
        END                                                         AS num_items,
        oc.sincronizado_en                                          AS alegra_sync_at
    FROM alegra.ordenes_compra oc;
    """)
    run(cur, "ALTER TABLE silver.ordenes_compra ADD PRIMARY KEY (alegra_id);")
    run(cur, "CREATE INDEX ON silver.ordenes_compra(proveedor_alegra_id);")
    run(cur, "CREATE INDEX ON silver.ordenes_compra(fecha);")
    run(cur, "CREATE INDEX ON silver.ordenes_compra(estado);")
    conn.commit()
    print(f"  OK - {count(cur, 'ordenes_compra'):,} filas")

    # ----------------------------------------------------------
    # silver.notas_credito - NUEVA
    # ----------------------------------------------------------
    print("\n[2.5] silver.notas_credito (NUEVA)...")
    run(cur, "DROP TABLE IF EXISTS silver.notas_credito CASCADE;")
    run(cur, """
    CREATE TABLE silver.notas_credito AS
    SELECT
        nc.id                                                       AS alegra_id,
        nc.cliente_id::text                                         AS cliente_alegra_id,
        nc.fecha,
        nc.estado,
        nc.subtotal,
        CASE
            WHEN nc.descuento IS NOT NULL AND nc.descuento::text ~ '^[0-9]+(\.[0-9]+)?$'
            THEN nc.descuento::text::numeric
            ELSE NULL
        END                                                         AS descuento_monto,
        CASE
            WHEN nc.impuesto IS NOT NULL AND nc.impuesto::text ~ '^[0-9]+(\.[0-9]+)?$'
            THEN nc.impuesto::text::numeric
            ELSE NULL
        END                                                         AS impuesto_monto,
        nc.total,
        nc.total_aplicado,
        nc.bodega_id,
        nc.centro_costo_id,
        nc.observaciones,
        nc.facturas_relacionadas,
        nc.items,
        nc.sincronizado_en                                          AS alegra_sync_at
    FROM alegra.notas_credito nc;
    """)
    run(cur, "ALTER TABLE silver.notas_credito ADD PRIMARY KEY (alegra_id);")
    run(cur, "CREATE INDEX ON silver.notas_credito(cliente_alegra_id);")
    run(cur, "CREATE INDEX ON silver.notas_credito(fecha);")
    run(cur, "CREATE INDEX ON silver.notas_credito(estado);")
    conn.commit()
    print(f"  OK - {count(cur, 'notas_credito'):,} filas")

    # ----------------------------------------------------------
    # silver.notas_debito - NUEVA
    # ----------------------------------------------------------
    print("\n[2.6] silver.notas_debito (NUEVA)...")
    run(cur, "DROP TABLE IF EXISTS silver.notas_debito CASCADE;")
    run(cur, """
    CREATE TABLE silver.notas_debito AS
    SELECT
        nd.id                                                       AS alegra_id,
        nd.cliente_id::text                                         AS cliente_alegra_id,
        nd.fecha,
        nd.tipo,
        nd.estado_emision                                           AS estado,
        nd.total,
        nd.saldo,
        nd.total_aplicado,
        nd.bodega_id,
        nd.centro_costo_id,
        nd.observaciones,
        nd.sincronizado_en                                          AS alegra_sync_at
    FROM alegra.notas_debito nd;
    """)
    run(cur, "ALTER TABLE silver.notas_debito ADD PRIMARY KEY (alegra_id);")
    run(cur, "CREATE INDEX ON silver.notas_debito(cliente_alegra_id);")
    run(cur, "CREATE INDEX ON silver.notas_debito(fecha);")
    conn.commit()
    print(f"  OK - {count(cur, 'notas_debito'):,} filas")

    # ============================================================
    # CATÁLOGOS
    # ============================================================

    print("\n" + "=" * 60)
    print("BLOQUE 3: CATÁLOGOS DE REFERENCIA")
    print("=" * 60)

    # silver.categorias_productos
    print("\n[3.1] silver.categorias_productos...")
    run(cur, "DROP TABLE IF EXISTS silver.categorias_productos CASCADE;")
    run(cur, """
    CREATE TABLE silver.categorias_productos AS
    SELECT id AS alegra_id, trim(nombre) AS nombre, descripcion, estado,
           sincronizado_en AS alegra_sync_at
    FROM alegra.categorias_productos;
    """)
    run(cur, "ALTER TABLE silver.categorias_productos ADD PRIMARY KEY (alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'categorias_productos'):,} filas")

    # silver.bodegas
    print("\n[3.2] silver.bodegas...")
    run(cur, "DROP TABLE IF EXISTS silver.bodegas CASCADE;")
    run(cur, """
    CREATE TABLE silver.bodegas AS
    SELECT id AS alegra_id, trim(nombre) AS nombre, es_principal, centro_costo_id, estado,
           sincronizado_en AS alegra_sync_at
    FROM alegra.bodegas;
    """)
    run(cur, "ALTER TABLE silver.bodegas ADD PRIMARY KEY (alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'bodegas'):,} filas")

    # silver.centros_costo
    print("\n[3.3] silver.centros_costo...")
    run(cur, "DROP TABLE IF EXISTS silver.centros_costo CASCADE;")
    run(cur, """
    CREATE TABLE silver.centros_costo AS
    SELECT id AS alegra_id, codigo, trim(nombre) AS nombre, descripcion, estado,
           sincronizado_en AS alegra_sync_at
    FROM alegra.centros_costo;
    """)
    run(cur, "ALTER TABLE silver.centros_costo ADD PRIMARY KEY (alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'centros_costo'):,} filas")

    # silver.impuestos
    print("\n[3.4] silver.impuestos...")
    run(cur, "DROP TABLE IF EXISTS silver.impuestos CASCADE;")
    run(cur, """
    CREATE TABLE silver.impuestos AS
    SELECT id AS alegra_id, trim(nombre) AS nombre, porcentaje, tipo, estado,
           sincronizado_en AS alegra_sync_at
    FROM alegra.impuestos;
    """)
    run(cur, "ALTER TABLE silver.impuestos ADD PRIMARY KEY (alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'impuestos'):,} filas")

    # silver.terminos_pago
    print("\n[3.5] silver.terminos_pago...")
    run(cur, "DROP TABLE IF EXISTS silver.terminos_pago CASCADE;")
    run(cur, """
    CREATE TABLE silver.terminos_pago AS
    SELECT id AS alegra_id, trim(nombre) AS nombre, dias, estado,
           sincronizado_en AS alegra_sync_at
    FROM alegra.terminos_pago;
    """)
    run(cur, "ALTER TABLE silver.terminos_pago ADD PRIMARY KEY (alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'terminos_pago'):,} filas")

    # silver.retenciones
    print("\n[3.6] silver.retenciones...")
    run(cur, "DROP TABLE IF EXISTS silver.retenciones CASCADE;")
    run(cur, """
    CREATE TABLE silver.retenciones AS
    SELECT id AS alegra_id, trim(nombre) AS nombre, porcentaje, tipo,
           tipo_retencion_606, calculado_por, descripcion, estado,
           sincronizado_en AS alegra_sync_at
    FROM alegra.retenciones;
    """)
    run(cur, "ALTER TABLE silver.retenciones ADD PRIMARY KEY (alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'retenciones'):,} filas")

    # silver.cuentas_bancarias
    print("\n[3.7] silver.cuentas_bancarias...")
    run(cur, "DROP TABLE IF EXISTS silver.cuentas_bancarias CASCADE;")
    run(cur, """
    CREATE TABLE silver.cuentas_bancarias AS
    SELECT id AS alegra_id, trim(nombre) AS nombre, numero, tipo, descripcion,
           saldo_inicial, fecha_saldo_inicial, estado,
           sincronizado_en AS alegra_sync_at
    FROM alegra.cuentas_bancarias;
    """)
    run(cur, "ALTER TABLE silver.cuentas_bancarias ADD PRIMARY KEY (alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'cuentas_bancarias'):,} filas")

    # ============================================================
    # VERIFICACIÓN FINAL
    # ============================================================

    print("\n" + "=" * 60)
    print("VERIFICACIÓN FINAL - CONTEO POR TABLA")
    print("=" * 60)

    tablas_silver = [
        'contactos', 'productos', 'facturas_venta', 'usuarios',
        'cotizaciones', 'pagos', 'facturas_compra', 'ordenes_compra',
        'notas_credito', 'notas_debito',
        'categorias_productos', 'bodegas', 'centros_costo',
        'impuestos', 'terminos_pago', 'retenciones', 'cuentas_bancarias'
    ]

    # también traer totales de alegra para las tablas que existen
    alegra_ref = {}
    tablas_alegra = [
        'contactos', 'productos', 'facturas_venta', 'usuarios',
        'cotizaciones', 'pagos', 'facturas_compra', 'ordenes_compra',
        'notas_credito', 'notas_debito',
        'categorias_productos', 'bodegas', 'centros_costo',
        'impuestos', 'terminos_pago', 'retenciones', 'cuentas_bancarias'
    ]
    for t in tablas_alegra:
        cur.execute(f"SELECT count(*) FROM alegra.{t}")
        alegra_ref[t] = cur.fetchone()[0]

    totales = {}
    total_silver = 0
    print(f"\n  {'Tabla':<25} {'ALEGRA':>8} {'SILVER':>8}  Estado")
    print(f"  {'-'*25} {'-'*8} {'-'*8}  ------")
    for t in tablas_silver:
        n = count(cur, t)
        totales[t] = n
        total_silver += n
        alegra_n = alegra_ref.get(t, '-')
        ok = "OK" if str(alegra_n) == str(n) else "REVISAR"
        print(f"  {t:<25} {str(alegra_n):>8} {n:>8}  {ok}")

    print(f"\n  TOTAL FILAS SILVER: {total_silver:,}")

    # Verificación adicional: contactos
    cur.execute("""
        SELECT
            count(*) FILTER (WHERE es_cliente) AS clientes,
            count(*) FILTER (WHERE es_proveedor) AS proveedores,
            count(*) FILTER (WHERE rnc = '0000000') AS sin_rnc,
            count(*) FILTER (WHERE dir_municipio IS NOT NULL) AS con_municipio,
            count(*) FILTER (WHERE limite_credito IS NOT NULL) AS con_credito
        FROM silver.contactos
    """)
    r = cur.fetchone()
    print(f"\n  Contactos: clientes={r[0]:,} proveedores={r[1]:,} sin_rnc={r[2]:,} con_municipio={r[3]:,} con_credito={r[4]:,}")

    # Verificación: cotizaciones por estado
    cur.execute("SELECT estado, count(*), sum(total) FROM silver.cotizaciones GROUP BY estado ORDER BY count(*) DESC")
    rows = cur.fetchall()
    print(f"\n  Cotizaciones por estado:")
    for r in rows:
        print(f"    {r[0]:<15} {r[1]:>6} | RD${float(r[2] or 0):>15,.2f}")

    # Verificación: pagos por tipo
    cur.execute("SELECT tipo, count(*), sum(monto) FROM silver.pagos GROUP BY tipo ORDER BY tipo")
    rows = cur.fetchall()
    print(f"\n  Pagos por tipo:")
    for r in rows:
        print(f"    tipo={r[0]} count={r[1]:,} monto=RD${float(r[2] or 0):>15,.2f}")

    # ============================================================
    # REPORTE FINAL
    # ============================================================
    print("\n")
    print("=" * 50)
    print("SCHEMA SILVER v2 CREADO")
    print("=" * 50)
    print(f"Tablas creadas: {len(tablas_silver)}")
    print()
    print("  TABLAS MEJORADAS:")
    for t in ['contactos', 'productos', 'facturas_venta', 'usuarios']:
        print(f"    silver.{t:<22} {totales[t]:>7,} filas")
    print()
    print("  TABLAS NUEVAS (transaccionales):")
    for t in ['cotizaciones', 'pagos', 'facturas_compra', 'ordenes_compra', 'notas_credito', 'notas_debito']:
        print(f"    silver.{t:<22} {totales[t]:>7,} filas")
    print()
    print("  CATALOGOS:")
    for t in ['categorias_productos', 'bodegas', 'centros_costo', 'impuestos', 'terminos_pago', 'retenciones', 'cuentas_bancarias']:
        print(f"    silver.{t:<22} {totales[t]:>7,} filas")
    print()
    print(f"  TOTAL FILAS: {total_silver:,}")
    print("=" * 50)

    cur.close()
    conn.close()
    print("\nConexion cerrada. Proceso completado.")

if __name__ == "__main__":
    main()
