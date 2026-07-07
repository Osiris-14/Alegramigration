"""
EXTRACT SILVER JSONB -> FLAT TABLES
Extrae todas las columnas JSONB de la capa Silver a tablas planas
y elimina las columnas JSONB originales.

11 nuevas tablas:
  - facturas_venta_items
  - facturas_venta_pagos_aplicados
  - cotizaciones_items
  - notas_credito_items
  - notas_credito_facturas_relacionadas
  - facturas_compra_compras
  - facturas_compra_pagos_aplicados
  - ordenes_compra_compras
  - pagos_facturas_aplicadas
  - productos_impuestos
  - productos_subitems
"""

import os
import psycopg2
from datetime import datetime

CONN_STRING = os.environ.get("SUPABASE_DB_URL")
if not CONN_STRING:
    raise ValueError("Falta variable de entorno SUPABASE_DB_URL")


def run(cur, sql, label=None):
    if label:
        print(f"  {label}...", end=" ", flush=True)
    cur.execute(sql)
    if label:
        print("OK")


def count(cur, table):
    cur.execute(f"SELECT count(*) FROM silver.{table}")
    return cur.fetchone()[0]


def main():
    print("=" * 60)
    print("EXTRACT JSONB -> FLAT TABLES - SILVER LAYER")
    print(f"Fecha: {datetime.now()}")
    print("=" * 60)

    conn = psycopg2.connect(CONN_STRING)
    conn.autocommit = False
    cur = conn.cursor()
    print("\nConexion exitosa\n")

    # ================================================================
    # BLOQUE 1: CREAR TABLAS PLANAS DESDE JSONB
    # ================================================================

    print("=" * 60)
    print("BLOQUE 1: CREACION DE TABLAS PLANAS")
    print("=" * 60)

    # ---------------------------------------------------------------
    # 1.1 facturas_venta_items
    # ---------------------------------------------------------------
    print("\n[1.1] silver.facturas_venta_items...")
    run(cur, "DROP TABLE IF EXISTS silver.facturas_venta_items CASCADE;")
    run(cur, """
    CREATE TABLE silver.facturas_venta_items AS
    SELECT
        fv.alegra_id AS factura_alegra_id,
        row_number() OVER (PARTITION BY fv.alegra_id) AS linea,
        (item->>'id')::integer AS item_id,
        item->>'name' AS nombre,
        item->>'unit' AS unidad,
        NULLIF(item->>'reference', '') AS referencia,
        item->>'itemType' AS tipo_item,
        NULLIF(item->>'description', '') AS descripcion,
        (item->>'quantity')::numeric AS cantidad,
        (item->>'price')::numeric AS precio_unitario,
        (item->>'discount')::numeric AS descuento_porcentaje,
        (item->>'discountAmount')::numeric AS descuento_monto,
        (item->>'total')::numeric AS total,
        item->>'discountType' AS tipo_descuento,
        NULLIF(item->>'idItemRemission', '') AS id_item_remision,
        item->'tax' AS impuestos
    FROM silver.facturas_venta fv,
         LATERAL jsonb_array_elements(fv.items) item
    """)
    run(cur, "ALTER TABLE silver.facturas_venta_items ADD PRIMARY KEY (factura_alegra_id, linea);")
    run(cur, "CREATE INDEX ON silver.facturas_venta_items(factura_alegra_id);")
    run(cur, "CREATE INDEX ON silver.facturas_venta_items(item_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'facturas_venta_items'):,} filas")

    # ---------------------------------------------------------------
    # 1.2 facturas_venta_pagos_aplicados
    # ---------------------------------------------------------------
    print("\n[1.2] silver.facturas_venta_pagos_aplicados...")
    run(cur, "DROP TABLE IF EXISTS silver.facturas_venta_pagos_aplicados CASCADE;")
    run(cur, """
    CREATE TABLE silver.facturas_venta_pagos_aplicados AS
    SELECT
        fv.alegra_id AS factura_alegra_id,
        row_number() OVER (PARTITION BY fv.alegra_id) AS linea,
        (pago->>'id')::integer AS pago_id,
        pago->>'number' AS numero_pago,
        NULLIF(pago->>'prefix', '') AS prefijo,
        pago->>'date' AS fecha,
        pago->>'status' AS estado,
        (pago->>'amount')::numeric AS monto,
        pago->>'paymentMethod' AS metodo_pago,
        NULLIF(pago->>'anotation', '') AS anotacion,
        NULLIF(pago->>'observations', '') AS observaciones
    FROM silver.facturas_venta fv,
         LATERAL jsonb_array_elements(fv.pagos_aplicados) pago
    """)
    run(cur, "ALTER TABLE silver.facturas_venta_pagos_aplicados ADD PRIMARY KEY (factura_alegra_id, linea);")
    run(cur, "CREATE INDEX ON silver.facturas_venta_pagos_aplicados(factura_alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'facturas_venta_pagos_aplicados'):,} filas")

    # ---------------------------------------------------------------
    # 1.3 cotizaciones_items
    # ---------------------------------------------------------------
    print("\n[1.3] silver.cotizaciones_items...")
    run(cur, "DROP TABLE IF EXISTS silver.cotizaciones_items CASCADE;")
    run(cur, """
    CREATE TABLE silver.cotizaciones_items AS
    SELECT
        c.alegra_id AS cotizacion_alegra_id,
        row_number() OVER (PARTITION BY c.alegra_id) AS linea,
        (item->>'id')::integer AS item_id,
        item->>'name' AS nombre,
        NULLIF(item->>'reference', '') AS referencia,
        NULLIF(item->>'description', '') AS descripcion,
        (item->>'quantity')::numeric AS cantidad,
        (item->>'price')::numeric AS precio_unitario,
        (item->>'discount')::numeric AS descuento_porcentaje,
        (item->>'total')::numeric AS total,
        item->'tax' AS impuestos
    FROM silver.cotizaciones c,
         LATERAL jsonb_array_elements(c.items) item
    """)
    run(cur, "ALTER TABLE silver.cotizaciones_items ADD PRIMARY KEY (cotizacion_alegra_id, linea);")
    run(cur, "CREATE INDEX ON silver.cotizaciones_items(cotizacion_alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'cotizaciones_items'):,} filas")

    # ---------------------------------------------------------------
    # 1.4 notas_credito_items
    # ---------------------------------------------------------------
    print("\n[1.4] silver.notas_credito_items...")
    run(cur, "DROP TABLE IF EXISTS silver.notas_credito_items CASCADE;")
    run(cur, """
    CREATE TABLE silver.notas_credito_items AS
    SELECT
        nc.alegra_id AS nota_credito_alegra_id,
        row_number() OVER (PARTITION BY nc.alegra_id) AS linea,
        (item->>'id')::integer AS item_id,
        item->>'name' AS nombre,
        NULLIF(item->>'reference', '') AS referencia,
        NULLIF(item->>'description', '') AS descripcion,
        (item->>'quantity')::numeric AS cantidad,
        (item->>'price')::numeric AS precio_unitario,
        (item->>'discount')::numeric AS descuento_porcentaje,
        (item->>'subtotal')::numeric AS subtotal,
        (item->>'total')::numeric AS total,
        item->'tax' AS impuestos
    FROM silver.notas_credito nc,
         LATERAL jsonb_array_elements(nc.items) item
    """)
    run(cur, "ALTER TABLE silver.notas_credito_items ADD PRIMARY KEY (nota_credito_alegra_id, linea);")
    run(cur, "CREATE INDEX ON silver.notas_credito_items(nota_credito_alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'notas_credito_items'):,} filas")

    # ---------------------------------------------------------------
    # 1.5 notas_credito_facturas_relacionadas
    # ---------------------------------------------------------------
    print("\n[1.5] silver.notas_credito_facturas_relacionadas...")
    run(cur, "DROP TABLE IF EXISTS silver.notas_credito_facturas_relacionadas CASCADE;")
    run(cur, """
    CREATE TABLE silver.notas_credito_facturas_relacionadas AS
    SELECT
        nc.alegra_id AS nota_credito_alegra_id,
        row_number() OVER (PARTITION BY nc.alegra_id) AS linea,
        (rel->>'id')::integer AS factura_id,
        rel->>'number' AS numero_factura,
        NULLIF(rel->>'prefix', '') AS prefijo,
        rel->>'fullNumber' AS numero_completo,
        rel->>'date' AS fecha,
        rel->>'dueDate' AS fecha_vencimiento,
        (rel->>'total')::numeric AS total_factura,
        (rel->>'amount')::numeric AS monto_aplicado,
        (rel->>'balance')::numeric AS saldo
    FROM silver.notas_credito nc,
         LATERAL jsonb_array_elements(nc.facturas_relacionadas) rel
    """)
    run(cur, "ALTER TABLE silver.notas_credito_facturas_relacionadas ADD PRIMARY KEY (nota_credito_alegra_id, linea);")
    run(cur, "CREATE INDEX ON silver.notas_credito_facturas_relacionadas(nota_credito_alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'notas_credito_facturas_relacionadas'):,} filas")

    # ---------------------------------------------------------------
    # 1.6 facturas_compra_compras (compras->'categories' array)
    # ---------------------------------------------------------------
    print("\n[1.6] silver.facturas_compra_compras...")
    run(cur, "DROP TABLE IF EXISTS silver.facturas_compra_compras CASCADE;")
    run(cur, """
    CREATE TABLE silver.facturas_compra_compras AS
    SELECT
        fc.alegra_id AS factura_compra_alegra_id,
        row_number() OVER (PARTITION BY fc.alegra_id) AS linea,
        (cat->>'id')::integer AS item_id,
        cat->>'name' AS nombre,
        (cat->>'quantity')::numeric AS cantidad,
        (cat->>'price')::numeric AS precio_unitario,
        (cat->>'discount')::numeric AS descuento,
        (cat->>'subtotal')::numeric AS subtotal,
        (cat->>'taxAmount')::numeric AS monto_impuesto,
        (cat->>'total')::numeric AS total,
        NULLIF(cat->>'observations', '') AS observaciones,
        cat->'tax' AS impuestos
    FROM silver.facturas_compra fc,
         LATERAL jsonb_array_elements(fc.compras->'categories') cat
    """)
    run(cur, "ALTER TABLE silver.facturas_compra_compras ADD PRIMARY KEY (factura_compra_alegra_id, linea);")
    run(cur, "CREATE INDEX ON silver.facturas_compra_compras(factura_compra_alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'facturas_compra_compras'):,} filas")

    # ---------------------------------------------------------------
    # 1.7 facturas_compra_pagos_aplicados
    # ---------------------------------------------------------------
    print("\n[1.7] silver.facturas_compra_pagos_aplicados...")
    run(cur, "DROP TABLE IF EXISTS silver.facturas_compra_pagos_aplicados CASCADE;")
    run(cur, """
    CREATE TABLE silver.facturas_compra_pagos_aplicados AS
    SELECT
        fc.alegra_id AS factura_compra_alegra_id,
        row_number() OVER (PARTITION BY fc.alegra_id) AS linea,
        (pago->>'id')::integer AS pago_id,
        pago->>'number' AS numero_pago,
        NULLIF(pago->>'prefix', '') AS prefijo,
        pago->>'date' AS fecha,
        pago->>'status' AS estado,
        (pago->>'amount')::numeric AS monto,
        pago->>'paymentMethod' AS metodo_pago,
        NULLIF(pago->>'anotation', '') AS anotacion,
        NULLIF(pago->>'observations', '') AS observaciones
    FROM silver.facturas_compra fc,
         LATERAL jsonb_array_elements(fc.pagos_aplicados) pago
    """)
    run(cur, "ALTER TABLE silver.facturas_compra_pagos_aplicados ADD PRIMARY KEY (factura_compra_alegra_id, linea);")
    run(cur, "CREATE INDEX ON silver.facturas_compra_pagos_aplicados(factura_compra_alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'facturas_compra_pagos_aplicados'):,} filas")

    # ---------------------------------------------------------------
    # 1.8 ordenes_compra_compras (compras->'categories' array)
    # ---------------------------------------------------------------
    print("\n[1.8] silver.ordenes_compra_compras...")
    run(cur, "DROP TABLE IF EXISTS silver.ordenes_compra_compras CASCADE;")
    run(cur, """
    CREATE TABLE silver.ordenes_compra_compras AS
    SELECT
        oc.alegra_id AS orden_compra_alegra_id,
        row_number() OVER (PARTITION BY oc.alegra_id) AS linea,
        (cat->>'id')::integer AS item_id,
        cat->>'name' AS nombre,
        (cat->>'quantity')::numeric AS cantidad,
        (cat->>'price')::numeric AS precio_unitario,
        (cat->>'discount')::numeric AS descuento,
        (cat->>'total')::numeric AS total,
        NULLIF(cat->>'observations', '') AS observaciones,
        cat->'tax' AS impuestos
    FROM silver.ordenes_compra oc,
         LATERAL jsonb_array_elements(oc.compras->'categories') cat
    """)
    run(cur, "ALTER TABLE silver.ordenes_compra_compras ADD PRIMARY KEY (orden_compra_alegra_id, linea);")
    run(cur, "CREATE INDEX ON silver.ordenes_compra_compras(orden_compra_alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'ordenes_compra_compras'):,} filas")

    # ---------------------------------------------------------------
    # 1.9 pagos_facturas_aplicadas
    # ---------------------------------------------------------------
    print("\n[1.9] silver.pagos_facturas_aplicadas...")
    run(cur, "DROP TABLE IF EXISTS silver.pagos_facturas_aplicadas CASCADE;")
    run(cur, """
    CREATE TABLE silver.pagos_facturas_aplicadas AS
    SELECT
        p.alegra_id AS pago_alegra_id,
        row_number() OVER (PARTITION BY p.alegra_id) AS linea,
        (fac->>'id')::integer AS factura_id,
        fac->>'number' AS numero_factura,
        fac->>'date' AS fecha,
        fac->>'dueDate' AS fecha_vencimiento,
        (fac->>'total')::numeric AS total_factura,
        (fac->>'amount')::numeric AS monto_aplicado
    FROM silver.pagos p,
         LATERAL jsonb_array_elements(p.facturas_aplicadas) fac
    """)
    run(cur, "ALTER TABLE silver.pagos_facturas_aplicadas ADD PRIMARY KEY (pago_alegra_id, linea);")
    run(cur, "CREATE INDEX ON silver.pagos_facturas_aplicadas(pago_alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'pagos_facturas_aplicadas'):,} filas")

    # ---------------------------------------------------------------
    # 1.10 productos_impuestos
    # ---------------------------------------------------------------
    print("\n[1.10] silver.productos_impuestos...")
    run(cur, "DROP TABLE IF EXISTS silver.productos_impuestos CASCADE;")
    run(cur, """
    CREATE TABLE silver.productos_impuestos AS
    SELECT
        p.alegra_id AS producto_alegra_id,
        row_number() OVER (PARTITION BY p.alegra_id) AS linea,
        imp->>'id' AS impuesto_id,
        imp->>'name' AS nombre,
        imp->>'type' AS tipo,
        imp->>'percentage' AS porcentaje,
        imp->>'status' AS estado,
        imp->>'deductible' AS deducible,
        NULLIF(imp->>'description', '') AS descripcion
    FROM silver.productos p,
         LATERAL jsonb_array_elements(p.impuestos_raw) imp
    """)
    run(cur, "ALTER TABLE silver.productos_impuestos ADD PRIMARY KEY (producto_alegra_id, linea);")
    run(cur, "CREATE INDEX ON silver.productos_impuestos(producto_alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'productos_impuestos'):,} filas")

    # ---------------------------------------------------------------
    # 1.11 productos_subitems
    # ---------------------------------------------------------------
    print("\n[1.11] silver.productos_subitems...")
    run(cur, "DROP TABLE IF EXISTS silver.productos_subitems CASCADE;")
    run(cur, """
    CREATE TABLE silver.productos_subitems AS
    SELECT
        p.alegra_id AS producto_alegra_id,
        row_number() OVER (PARTITION BY p.alegra_id) AS linea,
        (sub->>'quantity')::numeric AS cantidad,
        (sub->>'price')::numeric AS precio,
        sub->'item'->>'id' AS subitem_id,
        sub->'item'->>'name' AS nombre,
        sub->'item'->>'type' AS tipo,
        sub->'item'->>'status' AS estado,
        NULLIF(sub->'item'->>'reference', '') AS referencia,
        NULLIF(sub->'item'->>'description', '') AS descripcion,
        (sub->'item'->'inventory'->>'availableQuantity')::numeric AS stock_disponible,
        NULLIF(sub->'item'->'inventory'->>'unit', '') AS unidad,
        (sub->'item'->'inventory'->>'unitCost')::numeric AS costo_unitario
    FROM silver.productos p,
         LATERAL jsonb_array_elements(p.subitems) sub
    """)
    run(cur, "ALTER TABLE silver.productos_subitems ADD PRIMARY KEY (producto_alegra_id, linea);")
    run(cur, "CREATE INDEX ON silver.productos_subitems(producto_alegra_id);")
    conn.commit()
    print(f"  OK - {count(cur, 'productos_subitems'):,} filas")

    # ================================================================
    # BLOQUE 2: ELIMINAR COLUMNAS JSONB DE TABLAS ORIGEN
    # ================================================================

    print("\n" + "=" * 60)
    print("BLOQUE 2: ELIMINAR COLUMNAS JSONB DE TABLAS ORIGEN")
    print("=" * 60)

    drop_columns = [
        ("silver.facturas_venta", "items"),
        ("silver.facturas_venta", "pagos_aplicados"),
        ("silver.cotizaciones", "items"),
        ("silver.notas_credito", "items"),
        ("silver.notas_credito", "facturas_relacionadas"),
        ("silver.facturas_compra", "compras"),
        ("silver.facturas_compra", "retenciones"),
        ("silver.facturas_compra", "pagos_aplicados"),
        ("silver.ordenes_compra", "compras"),
        ("silver.pagos", "facturas_aplicadas"),
        ("silver.productos", "impuestos_raw"),
        ("silver.productos", "subitems"),
    ]

    for table, col in drop_columns:
        print(f"  {table}.{col}...", end=" ", flush=True)
        try:
            run(cur, f"ALTER TABLE {table} DROP COLUMN IF EXISTS {col}")
            print("OK")
        except Exception as e:
            print(f"ERROR: {e}")
    conn.commit()

    # ================================================================
    # BLOQUE 3: AGREGAR FOREIGN KEYS
    # ================================================================

    print("\n" + "=" * 60)
    print("BLOQUE 3: FOREIGN KEYS")
    print("=" * 60)

    fks = [
        ("facturas_venta_items", "factura_alegra_id", "facturas_venta", "alegra_id"),
        ("facturas_venta_pagos_aplicados", "factura_alegra_id", "facturas_venta", "alegra_id"),
        ("cotizaciones_items", "cotizacion_alegra_id", "cotizaciones", "alegra_id"),
        ("notas_credito_items", "nota_credito_alegra_id", "notas_credito", "alegra_id"),
        ("notas_credito_facturas_relacionadas", "nota_credito_alegra_id", "notas_credito", "alegra_id"),
        ("facturas_compra_compras", "factura_compra_alegra_id", "facturas_compra", "alegra_id"),
        ("facturas_compra_pagos_aplicados", "factura_compra_alegra_id", "facturas_compra", "alegra_id"),
        ("ordenes_compra_compras", "orden_compra_alegra_id", "ordenes_compra", "alegra_id"),
        ("pagos_facturas_aplicadas", "pago_alegra_id", "pagos", "alegra_id"),
        ("productos_impuestos", "producto_alegra_id", "productos", "alegra_id"),
        ("productos_subitems", "producto_alegra_id", "productos", "alegra_id"),
    ]

    for table, fk_col, ref_table, ref_col in fks:
        fk_name = f"fk_{table}_{fk_col}"
        print(f"  silver.{table}.{fk_col} -> silver.{ref_table}.{ref_col}...", end=" ", flush=True)
        try:
            run(cur, f"""
                ALTER TABLE silver.{table}
                ADD CONSTRAINT {fk_name}
                FOREIGN KEY ({fk_col})
                REFERENCES silver.{ref_table}({ref_col})
                ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED
            """)
            print("OK")
        except Exception as e:
            print(f"ERROR: {e}")
    conn.commit()

    # ================================================================
    # VERIFICACION FINAL
    # ================================================================

    print("\n" + "=" * 60)
    print("VERIFICACION FINAL")
    print("=" * 60)

    all_tables = [
        "contactos", "productos", "facturas_venta", "usuarios",
        "cotizaciones", "pagos", "facturas_compra", "ordenes_compra",
        "notas_credito", "notas_debito",
        "categorias_productos", "bodegas", "centros_costo",
        "impuestos", "terminos_pago", "retenciones", "cuentas_bancarias",
        "facturas_venta_items",
        "facturas_venta_pagos_aplicados",
        "cotizaciones_items",
        "notas_credito_items",
        "notas_credito_facturas_relacionadas",
        "facturas_compra_compras",
        "facturas_compra_pagos_aplicados",
        "ordenes_compra_compras",
        "pagos_facturas_aplicadas",
        "productos_impuestos",
        "productos_subitems",
    ]

    print(f"\n  {'Tabla':<40} {'Filas':>10}")
    print(f"  {'-'*40} {'-'*10}")
    total = 0
    for t in all_tables:
        n = count(cur, t)
        total += n
        print(f"  {t:<40} {n:>10,}")
    print(f"  {'-'*40} {'-'*10}")
    print(f"  {'TOTAL':<40} {total:>10,}")

    print("\n  Verificando columnas JSONB residuales...")
    cur.execute("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'silver'
          AND data_type = 'jsonb'
        ORDER BY table_name, column_name
    """)
    remaining = cur.fetchall()
    if remaining:
        print(f"  ATENCION - Quedan {len(remaining)} columna(s) JSONB:")
        for r in remaining:
            print(f"    silver.{r[0]}.{r[1]} ({r[2]})")
    else:
        print("  No quedan columnas JSONB en el schema silver.")

    print("\n" + "=" * 60)
    print("PROCESO COMPLETADO EXITOSAMENTE")
    print("=" * 60)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
