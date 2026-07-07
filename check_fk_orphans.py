"""Check FK orphans and add constraints"""
import psycopg2

CONN = 'postgresql://postgres.xilcckvfaawcmjeazhku:Supebase2030*@aws-1-us-east-1.pooler.supabase.com:5432/postgres'
conn = psycopg2.connect(CONN)
cur = conn.cursor()

# Check PK types
cur.execute("""
    SELECT table_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'silver' AND column_name = 'alegra_id'
    ORDER BY table_name
""")
print("=== PK (alegra_id) data types ===")
for r in cur.fetchall():
    print(f"  {r[0]:<30} {r[1]}")

# Relationships: (child_table, fk_col, parent_table)
relations = [
    ('facturas_venta',   'cliente_alegra_id',   'contactos'),
    ('facturas_venta',   'vendedor_alegra_id',  'usuarios'),
    ('facturas_venta',   'bodega_id',           'bodegas'),
    ('facturas_venta',   'centro_costo_id',     'centros_costo'),
    ('facturas_venta',   'termino_pago_id',     'terminos_pago'),
    ('cotizaciones',     'cliente_alegra_id',   'contactos'),
    ('cotizaciones',     'vendedor_alegra_id',  'usuarios'),
    ('cotizaciones',     'bodega_id',           'bodegas'),
    ('cotizaciones',     'centro_costo_id',     'centros_costo'),
    ('pagos',            'contacto_alegra_id',  'contactos'),
    ('pagos',            'cuenta_bancaria_id',  'cuentas_bancarias'),
    ('pagos',            'centro_costo_id',     'centros_costo'),
    ('facturas_compra',  'proveedor_alegra_id', 'contactos'),
    ('facturas_compra',  'bodega_id',           'bodegas'),
    ('facturas_compra',  'centro_costo_id',     'centros_costo'),
    ('ordenes_compra',   'proveedor_alegra_id', 'contactos'),
    ('ordenes_compra',   'bodega_id',           'bodegas'),
    ('ordenes_compra',   'centro_costo_id',     'centros_costo'),
    ('notas_credito',    'cliente_alegra_id',   'contactos'),
    ('notas_credito',    'bodega_id',           'bodegas'),
    ('notas_debito',     'cliente_alegra_id',   'contactos'),
    ('notas_debito',     'bodega_id',           'bodegas'),
    ('productos',        'categoria_id',        'categorias_productos'),
    ('contactos',        'vendedor_id',         'usuarios'),
    ('contactos',        'termino_pago_id',     'terminos_pago'),
]

print("\n=== ORPHAN CHECK ===")
orphan_results = []
for child_t, fk_col, parent_t in relations:
    cur.execute(f"""
        SELECT count(*) FROM silver.{child_t} c
        WHERE c.{fk_col} IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM silver.{parent_t} p
              WHERE p.alegra_id::text = c.{fk_col}::text
          )
    """)
    orphans = cur.fetchone()[0]
    rel = f"{child_t}.{fk_col} -> {parent_t}"
    action = "OK-direct FK" if orphans == 0 else f"ORPHANS={orphans} -> set NULL"
    print(f"  {rel:<58} {action}")
    orphan_results.append((child_t, fk_col, parent_t, orphans))

conn.close()
print("\nDone.")
