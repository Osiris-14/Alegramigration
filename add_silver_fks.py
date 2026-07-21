"""
Agrega FOREIGN KEY constraints al schema SILVER.
Estrategia:
  - Si hay orphans: poner esa FK en NULL antes de crear el constraint
  - Si no hay orphans: crear FK directamente
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

CONN = os.environ.get("SUPABASE_DB_URL")
if not CONN:
    print("ERROR: variable SUPABASE_DB_URL no definida (.env o entorno)")
    sys.exit(1)

conn = psycopg2.connect(CONN)
conn.autocommit = False
cur = conn.cursor()

# (child_table, fk_col, parent_table, orphan_count_from_audit)
relations = [
    ('facturas_venta',   'cliente_alegra_id',   'contactos',           2),
    ('facturas_venta',   'vendedor_alegra_id',  'usuarios',            0),
    ('facturas_venta',   'bodega_id',           'bodegas',             0),
    ('facturas_venta',   'centro_costo_id',     'centros_costo',       0),
    ('facturas_venta',   'termino_pago_id',     'terminos_pago',       0),
    ('cotizaciones',     'cliente_alegra_id',   'contactos',        4281),
    ('cotizaciones',     'vendedor_alegra_id',  'usuarios',            3),
    ('cotizaciones',     'bodega_id',           'bodegas',             0),
    ('cotizaciones',     'centro_costo_id',     'centros_costo',       0),
    ('pagos',            'contacto_alegra_id',  'contactos',         509),
    ('pagos',            'cuenta_bancaria_id',  'cuentas_bancarias',8993),
    ('pagos',            'centro_costo_id',     'centros_costo',       0),
    ('facturas_compra',  'proveedor_alegra_id', 'contactos',           1),
    ('facturas_compra',  'bodega_id',           'bodegas',             0),
    ('facturas_compra',  'centro_costo_id',     'centros_costo',       0),
    ('ordenes_compra',   'proveedor_alegra_id', 'contactos',           0),
    ('ordenes_compra',   'bodega_id',           'bodegas',             0),
    ('ordenes_compra',   'centro_costo_id',     'centros_costo',       0),
    ('notas_credito',    'cliente_alegra_id',   'contactos',           0),
    ('notas_credito',    'bodega_id',           'bodegas',             0),
    ('notas_debito',     'cliente_alegra_id',   'contactos',           0),
    ('notas_debito',     'bodega_id',           'bodegas',             0),
    ('productos',        'categoria_id',        'categorias_productos',0),
    ('contactos',        'vendedor_id',         'usuarios',            1),
    ('contactos',        'termino_pago_id',     'terminos_pago',       0),
]

print("=" * 65)
print("AGREGANDO FOREIGN KEYS AL SCHEMA SILVER")
print("=" * 65)

nullified = []
fk_created = []
fk_failed = []

for child_t, fk_col, parent_t, orphans in relations:
    fk_name = f"fk_{child_t}_{fk_col}"
    rel = f"{child_t}.{fk_col} -> {parent_t}"

    # Verificar que ambas tablas existen antes de tocar nada
    cur.execute("""
        SELECT
            EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='silver' AND table_name=%s),
            EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='silver' AND table_name=%s)
    """, (child_t, parent_t))
    child_exists, parent_exists = cur.fetchone()
    if not child_exists or not parent_exists:
        print(f"  [SKIP] {rel}  -> falta tabla (child={child_exists}, parent={parent_exists})")
        fk_failed.append((rel, "tabla inexistente"))
        continue

    # Step 1: Drop existing FK if exists (idempotent)
    cur.execute(f"""
        ALTER TABLE silver.{child_t}
        DROP CONSTRAINT IF EXISTS {fk_name};
    """)

    # Step 2: Nullify orphans si la columna existe
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='silver' AND table_name=%s AND column_name=%s
        )
    """, (child_t, fk_col))
    col_exists = cur.fetchone()[0]
    if not col_exists:
        print(f"  [SKIP] {rel}  -> columna {fk_col} no existe en silver.{child_t}")
        fk_failed.append((rel, f"columna {fk_col} inexistente"))
        continue

    # Recalcular orphans reales (no confiar en el hardcoded)
    cur.execute(f"""
        SELECT count(*) FROM silver.{child_t} c
        WHERE c.{fk_col} IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM silver.{parent_t} p
              WHERE p.alegra_id::text = c.{fk_col}::text
          )
    """)
    real_orphans = cur.fetchone()[0]
    if real_orphans > 0:
        cur.execute(f"""
            UPDATE silver.{child_t}
            SET {fk_col} = NULL
            WHERE {fk_col} IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM silver.{parent_t} p
                  WHERE p.alegra_id::text = {child_t}.{fk_col}::text
              );
        """)
        print(f"  [NULL] {rel}  -> {real_orphans} orphans puestos en NULL")
        nullified.append((rel, real_orphans))

    # Step 3: Add FK constraint
    try:
        cur.execute(f"""
            ALTER TABLE silver.{child_t}
            ADD CONSTRAINT {fk_name}
            FOREIGN KEY ({fk_col})
            REFERENCES silver.{parent_t} (alegra_id)
            ON DELETE SET NULL
            DEFERRABLE INITIALLY DEFERRED;
        """)
        conn.commit()
        fk_created.append(rel)
        print(f"  [FK]   {rel}  OK")
    except Exception as e:
        conn.rollback()
        print(f"  [FAIL] {rel}  -> {e}")
        fk_failed.append((rel, str(e)[:200]))

# ============================================================
# VERIFICACION: listar todos los FKs creados
# ============================================================
print()
print("=" * 65)
print("VERIFICACION: FOREIGN KEYS EN SCHEMA SILVER")
print("=" * 65)
cur.execute("""
    SELECT
        tc.table_name                          AS tabla_hijo,
        kcu.column_name                        AS columna_fk,
        ccu.table_name                         AS tabla_padre,
        ccu.column_name                        AS columna_pk,
        tc.constraint_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage ccu
        ON ccu.constraint_name = tc.constraint_name
        AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'silver'
    ORDER BY tc.table_name, kcu.column_name;
""")
rows = cur.fetchall()
print(f"\n  {'Tabla hijo':<22} {'FK col':<25} {'-> Tabla padre':<25} {'PK col'}")
print(f"  {'-'*22} {'-'*25} {'-'*25} {'-'*12}")
for r in rows:
    print(f"  {r[0]:<22} {r[1]:<25} {r[2]:<25} {r[3]}")

print(f"\n  Total FKs creadas: {len(rows)}")

# ============================================================
# REPORTE
# ============================================================
print()
print("=" * 65)
print("REPORTE FINAL")
print("=" * 65)
print(f"  FKs creadas:          {len(fk_created)}")
print(f"  Relaciones con NULL:  {len(nullified)}")
print(f"  FKs fallidas:         {len(fk_failed)}")
if nullified:
    print("  Detalle de orphans resueltos:")
    for rel, n in nullified:
        print(f"    {rel}  ({n} puestos en NULL)")
if fk_failed:
    print("  Detalle de FKs fallidas:")
    for rel, motivo in fk_failed:
        print(f"    {rel}  -> {motivo}")

cur.close()
conn.close()
print("\nConexion cerrada. FKs aplicadas correctamente.")
