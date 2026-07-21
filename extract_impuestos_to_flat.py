"""
EXTRACT remaining impuestos JSONB from items tables
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
    print("EXTRACT IMPUESTOS JSONB -> FLAT TABLES")
    print(f"Fecha: {datetime.now()}")
    print("=" * 60)

    conn = psycopg2.connect(CONN_STRING)
    conn.autocommit = False
    cur = conn.cursor()
    print("\nConexion exitosa\n")

    # ---------------------------------------------------------------
    # 1. facturas_venta_items_impuestos
    # ---------------------------------------------------------------
    print("[1] silver.facturas_venta_items_impuestos...")
    run(cur, "DROP TABLE IF EXISTS silver.facturas_venta_items_impuestos CASCADE;")
    run(cur, """
    CREATE TABLE silver.facturas_venta_items_impuestos AS
    WITH items_con_impuestos AS (
        SELECT * FROM silver.facturas_venta_items
        WHERE jsonb_typeof(impuestos) = 'array' AND impuestos::text != '[]'
    )
    SELECT
        i.factura_alegra_id,
        i.linea AS item_linea,
        row_number() OVER (PARTITION BY i.factura_alegra_id, i.linea) AS impuesto_linea,
        imp->>'id' AS impuesto_id,
        NULLIF(imp->>'name', '') AS nombre,
        NULLIF(imp->>'type', '') AS tipo,
        NULLIF(imp->>'amount', '')::numeric AS monto,
        NULLIF(imp->>'percentage', '') AS porcentaje,
        NULLIF(imp->>'status', '') AS estado,
        NULLIF(imp->>'description', '') AS descripcion
    FROM items_con_impuestos i,
         LATERAL jsonb_array_elements(i.impuestos) imp
    """)
    run(cur, "ALTER TABLE silver.facturas_venta_items_impuestos ADD PRIMARY KEY (factura_alegra_id, item_linea, impuesto_linea);")
    run(cur, "CREATE INDEX ON silver.facturas_venta_items_impuestos(factura_alegra_id, item_linea);")
    conn.commit()
    print(f"  OK - {count(cur, 'facturas_venta_items_impuestos'):,} filas")

    # ---------------------------------------------------------------
    # 2. cotizaciones_items_impuestos
    # ---------------------------------------------------------------
    print("[2] silver.cotizaciones_items_impuestos...")
    run(cur, "DROP TABLE IF EXISTS silver.cotizaciones_items_impuestos CASCADE;")
    run(cur, """
    CREATE TABLE silver.cotizaciones_items_impuestos AS
    WITH items_con_impuestos AS (
        SELECT * FROM silver.cotizaciones_items
        WHERE jsonb_typeof(impuestos) = 'array' AND impuestos::text != '[]'
    )
    SELECT
        i.cotizacion_alegra_id,
        i.linea AS item_linea,
        row_number() OVER (PARTITION BY i.cotizacion_alegra_id, i.linea) AS impuesto_linea,
        imp->>'id' AS impuesto_id,
        NULLIF(imp->>'name', '') AS nombre,
        NULLIF(imp->>'type', '') AS tipo,
        NULLIF(imp->>'amount', '')::numeric AS monto,
        NULLIF(imp->>'percentage', '') AS porcentaje,
        NULLIF(imp->>'status', '') AS estado,
        CASE
            WHEN imp->>'deductible' IN ('true', 'false') THEN (imp->>'deductible')::boolean
            ELSE NULL
        END AS deducible,
        NULLIF(imp->>'description', '') AS descripcion
    FROM items_con_impuestos i,
         LATERAL jsonb_array_elements(i.impuestos) imp
    """)
    run(cur, "ALTER TABLE silver.cotizaciones_items_impuestos ADD PRIMARY KEY (cotizacion_alegra_id, item_linea, impuesto_linea);")
    run(cur, "CREATE INDEX ON silver.cotizaciones_items_impuestos(cotizacion_alegra_id, item_linea);")
    conn.commit()
    print(f"  OK - {count(cur, 'cotizaciones_items_impuestos'):,} filas")

    # ---------------------------------------------------------------
    # 3. notas_credito_items_impuestos
    # ---------------------------------------------------------------
    print("[3] silver.notas_credito_items_impuestos...")
    run(cur, "DROP TABLE IF EXISTS silver.notas_credito_items_impuestos CASCADE;")
    run(cur, """
    CREATE TABLE silver.notas_credito_items_impuestos AS
    WITH items_con_impuestos AS (
        SELECT * FROM silver.notas_credito_items
        WHERE jsonb_typeof(impuestos) = 'array' AND impuestos::text != '[]'
    )
    SELECT
        i.nota_credito_alegra_id,
        i.linea AS item_linea,
        row_number() OVER (PARTITION BY i.nota_credito_alegra_id, i.linea) AS impuesto_linea,
        imp->>'id' AS impuesto_id,
        NULLIF(imp->>'name', '') AS nombre,
        NULLIF(imp->>'type', '') AS tipo,
        NULLIF(imp->>'amount', '')::numeric AS monto,
        NULLIF(imp->>'percentage', '') AS porcentaje,
        NULLIF(imp->>'status', '') AS estado,
        NULLIF(imp->>'description', '') AS descripcion
    FROM items_con_impuestos i,
         LATERAL jsonb_array_elements(i.impuestos) imp
    """)
    run(cur, "ALTER TABLE silver.notas_credito_items_impuestos ADD PRIMARY KEY (nota_credito_alegra_id, item_linea, impuesto_linea);")
    run(cur, "CREATE INDEX ON silver.notas_credito_items_impuestos(nota_credito_alegra_id, item_linea);")
    conn.commit()
    print(f"  OK - {count(cur, 'notas_credito_items_impuestos'):,} filas")

    # ---------------------------------------------------------------
    # 4. facturas_compra_compras_impuestos
    # ---------------------------------------------------------------
    print("[4] silver.facturas_compra_compras_impuestos...")
    run(cur, "DROP TABLE IF EXISTS silver.facturas_compra_compras_impuestos CASCADE;")
    run(cur, """
    CREATE TABLE silver.facturas_compra_compras_impuestos AS
    WITH items_con_impuestos AS (
        SELECT * FROM silver.facturas_compra_compras
        WHERE impuestos IS NOT NULL
          AND jsonb_typeof(impuestos) = 'array'
          AND impuestos::text != '[]'
    )
    SELECT
        i.factura_compra_alegra_id,
        i.linea AS item_linea,
        row_number() OVER (PARTITION BY i.factura_compra_alegra_id, i.linea) AS impuesto_linea,
        imp->>'id' AS impuesto_id,
        NULLIF(imp->>'name', '') AS nombre,
        NULLIF(imp->>'type', '') AS tipo,
        NULLIF(imp->>'amount', '')::numeric AS monto,
        NULLIF(imp->>'percentage', '') AS porcentaje,
        NULLIF(imp->>'status', '') AS estado,
        CASE
            WHEN imp->>'deductible' IN ('true', 'false') THEN (imp->>'deductible')::boolean
            ELSE NULL
        END AS deducible,
        NULLIF(imp->>'description', '') AS descripcion
    FROM items_con_impuestos i,
         LATERAL jsonb_array_elements(i.impuestos) imp
    """)
    run(cur, "ALTER TABLE silver.facturas_compra_compras_impuestos ADD PRIMARY KEY (factura_compra_alegra_id, item_linea, impuesto_linea);")
    run(cur, "CREATE INDEX ON silver.facturas_compra_compras_impuestos(factura_compra_alegra_id, item_linea);")
    conn.commit()
    print(f"  OK - {count(cur, 'facturas_compra_compras_impuestos'):,} filas")

    # ---------------------------------------------------------------
    # 5. ordenes_compra_compras_impuestos
    # ---------------------------------------------------------------
    print("[5] silver.ordenes_compra_compras_impuestos...")
    run(cur, "DROP TABLE IF EXISTS silver.ordenes_compra_compras_impuestos CASCADE;")
    run(cur, """
    CREATE TABLE silver.ordenes_compra_compras_impuestos AS
    WITH items_con_impuestos AS (
        SELECT * FROM silver.ordenes_compra_compras
        WHERE jsonb_typeof(impuestos) = 'array' AND impuestos::text != '[]'
    )
    SELECT
        i.orden_compra_alegra_id,
        i.linea AS item_linea,
        row_number() OVER (PARTITION BY i.orden_compra_alegra_id, i.linea) AS impuesto_linea,
        imp->>'id' AS impuesto_id,
        NULLIF(imp->>'name', '') AS nombre,
        NULLIF(imp->>'type', '') AS tipo,
        NULLIF(imp->>'amount', '')::numeric AS monto,
        NULLIF(imp->>'percentage', '') AS porcentaje,
        NULLIF(imp->>'status', '') AS estado,
        CASE
            WHEN imp->>'deductible' IN ('true', 'false') THEN (imp->>'deductible')::boolean
            ELSE NULL
        END AS deducible,
        NULLIF(imp->>'description', '') AS descripcion
    FROM items_con_impuestos i,
         LATERAL jsonb_array_elements(i.impuestos) imp
    """)
    run(cur, "ALTER TABLE silver.ordenes_compra_compras_impuestos ADD PRIMARY KEY (orden_compra_alegra_id, item_linea, impuesto_linea);")
    run(cur, "CREATE INDEX ON silver.ordenes_compra_compras_impuestos(orden_compra_alegra_id, item_linea);")
    conn.commit()
    print(f"  OK - {count(cur, 'ordenes_compra_compras_impuestos'):,} filas")

    # ---------------------------------------------------------------
    # BLOQUE 2: DROP impuestos columns
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print("BLOQUE 2: ELIMINAR COLUMNAS impuestos")
    print("=" * 60)

    drops = [
        "silver.facturas_venta_items",
        "silver.cotizaciones_items",
        "silver.notas_credito_items",
        "silver.facturas_compra_compras",
        "silver.ordenes_compra_compras",
    ]
    for t in drops:
        print(f"  {t}.impuestos...", end=" ", flush=True)
        try:
            run(cur, f"ALTER TABLE {t} DROP COLUMN IF EXISTS impuestos")
            print("OK")
        except Exception as e:
            print(f"ERROR: {e}")
    conn.commit()

    # ---------------------------------------------------------------
    # BLOQUE 3: FOREIGN KEYS
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print("BLOQUE 3: FOREIGN KEYS")
    print("=" * 60)

    fks = [
        ("facturas_venta_items_impuestos", "factura_alegra_id, item_linea", "facturas_venta_items", "factura_alegra_id, linea"),
        ("cotizaciones_items_impuestos", "cotizacion_alegra_id, item_linea", "cotizaciones_items", "cotizacion_alegra_id, linea"),
        ("notas_credito_items_impuestos", "nota_credito_alegra_id, item_linea", "notas_credito_items", "nota_credito_alegra_id, linea"),
        ("facturas_compra_compras_impuestos", "factura_compra_alegra_id, item_linea", "facturas_compra_compras", "factura_compra_alegra_id, linea"),
        ("ordenes_compra_compras_impuestos", "orden_compra_alegra_id, item_linea", "ordenes_compra_compras", "orden_compra_alegra_id, linea"),
    ]

    for table, fk_cols, ref_table, ref_cols in fks:
        fk_name = f"fk_{table}"
        print(f"  silver.{table}.({fk_cols}) -> silver.{ref_table}.({ref_cols})...", end=" ", flush=True)
        try:
            run(cur, f"ALTER TABLE silver.{table} DROP CONSTRAINT IF EXISTS {fk_name}")
            run(cur, f"""
                ALTER TABLE silver.{table}
                ADD CONSTRAINT {fk_name}
                FOREIGN KEY ({fk_cols})
                REFERENCES silver.{ref_table}({ref_cols})
                ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED
            """)
            print("OK")
        except Exception as e:
            print(f"ERROR: {e}")
    conn.commit()

    # ---------------------------------------------------------------
    # VERIFICACION
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print("VERIFICACION FINAL")
    print("=" * 60)

    tables = [
        "facturas_venta_items_impuestos",
        "cotizaciones_items_impuestos",
        "notas_credito_items_impuestos",
        "facturas_compra_compras_impuestos",
        "ordenes_compra_compras_impuestos",
    ]

    print(f"\n  {'Tabla':<50} {'Filas':>10}")
    print(f"  {'-'*50} {'-'*10}")
    total = 0
    for t in tables:
        n = count(cur, t)
        total += n
        print(f"  {t:<50} {n:>10,}")
    print(f"  {'-'*50} {'-'*10}")
    print(f"  {'TOTAL':<50} {total:>10,}")

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
    print("PROCESO COMPLETADO")
    print("=" * 60)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
