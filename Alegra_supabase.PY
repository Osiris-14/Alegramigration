"""
Alegra -> Supabase: tablas en español con columnas reales
=============================================================
Corre esto en Claude Code.

.env necesita:
  ALEGRA_EMAIL
  ALEGRA_TOKEN
  SUPABASE_DB_URL   (Supabase: Settings > Database > Connection string > URI.
                      Si falla la conexión, agrégale ?sslmode=require al final)

pip install requests python-dotenv psycopg2-binary --break-system-packages

Qué hace:
  - Crea el schema "alegra" en Supabase
  - Crea 27 tablas en español con columnas reales extraídas de los campos
    de Alegra (cliente_id, fecha, total, etc.) — no solo un jsonb genérico
  - Cada tabla además tiene "datos_originales" jsonb con el registro
    completo, por si necesitas algo que no mapeamos explícitamente
  - Pagina respetando el rate limit de Alegra (150 req/min)
  - Hace upsert: puedes volver a correrlo sin duplicar nada

Basado en el inventario real de esta cuenta (~87k registros, sobre todo
en pagos, cotizaciones, contactos, facturas de venta y facturas de compra).
Tiempo estimado: 20-25 minutos por el rate limit.

NO se crean (vacías en esta cuenta, agrégalas después si las usas):
variant_attributes, warehouse_transfers, recurring_invoices,
global_invoices, income_debit_notes, transportation_receipts.

NOTA sobre "impuestos": el endpoint de Alegra devuelve un formato distinto
a los demás ({results, total} en vez de {data, metadata}), así que las
columnas de esa tabla son una mejor suposición — revisa "datos_originales"
si algo no calza ahí.

Los renglones de detalle (items de factura, compras, asientos contables)
se guardan como jsonb dentro de cada tabla por ahora. Si después necesitas
reportes a nivel de línea (ej: "qué productos se vendieron más"), se puede
normalizar eso en tablas hijas — dilo y lo armamos.
"""

import os
import time
import base64
import requests
import psycopg2
from psycopg2.extras import execute_values, Json
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.environ["ALEGRA_EMAIL"]
TOKEN = os.environ["ALEGRA_TOKEN"]
DB_URL = os.environ["SUPABASE_DB_URL"]
BASE_URL = "https://api.alegra.com/api/v1"

auth_string = base64.b64encode(f"{EMAIL}:{TOKEN}".encode()).decode()
HEADERS = {"Authorization": f"Basic {auth_string}", "Accept": "application/json"}

PAGE_SIZE = 30
SCHEMA = "alegra"


def g(d, path, default=None):
    """Acceso seguro a campos anidados: g(record, 'client.id')"""
    cur = d
    if not isinstance(d, dict):
        return default
    for part in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
        if cur is None:
            return default
    return cur


# Cada entrada: tabla destino, endpoint, columnas [(nombre, tipo, ruta)],
# pk_campo (default "id"), singular (default False, para /company)
TABLES = {

    # ---- catálogos / configuración ----
    "item_categories": {
        "tabla": "categorias_productos", "endpoint": "/item-categories",
        "columnas": [
            ("nombre", "text", "name"),
            ("descripcion", "text", "description"),
            ("estado", "text", "status"),
        ],
    },
    "price_lists": {
        "tabla": "listas_precio", "endpoint": "/price-lists",
        "columnas": [
            ("nombre", "text", "name"),
            ("tipo", "text", "type"),
            ("principal", "boolean", "main"),
            ("moneda", "jsonb", "currency"),
            ("estado", "text", "status"),
        ],
    },
    "custom_fields": {
        "tabla": "campos_adicionales", "endpoint": "/custom-fields",
        "columnas": [
            ("nombre", "text", "name"),
            ("clave", "text", "key"),
            ("tipo", "text", "type"),
            ("descripcion", "text", "description"),
            ("valor_predeterminado", "jsonb", "defaultValue"),
            ("configuracion", "jsonb", "settings"),
            ("estado", "text", "status"),
        ],
    },
    "warehouses": {
        "tabla": "bodegas", "endpoint": "/warehouses",
        "columnas": [
            ("nombre", "text", "name"),
            ("es_principal", "boolean", "isDefault"),
            ("centro_costo_id", "text", "costCenter.id"),
            ("estado", "text", "status"),
        ],
    },
    "number_templates": {
        "tabla": "plantillas_numeracion", "endpoint": "/number-templates",
        "columnas": [
            ("nombre", "text", "name"),
            ("prefijo", "text", "prefix"),
            ("tipo_documento", "text", "documentType"),
            ("tipo_subdocumento", "jsonb", "subDocumentType"),
            ("es_principal", "boolean", "isDefault"),
            ("es_electronica", "boolean", "isElectronic"),
            ("autoincremento", "boolean", "autoincrement"),
            ("siguiente_numero", "numeric", "nextInvoiceNumber"),
            ("numero_maximo", "numeric", "maxInvoiceNumber"),
            ("fecha_inicio", "date", "startDate"),
            ("fecha_fin", "date", "endDate"),
            ("estado", "text", "status"),
        ],
    },
    "taxes": {
        "tabla": "impuestos", "endpoint": "/taxes",
        "columnas": [
            ("nombre", "text", "name"),
            ("porcentaje", "numeric", "percentage"),
            ("tipo", "text", "type"),
            ("estado", "text", "status"),
        ],
    },
    "retentions": {
        "tabla": "retenciones", "endpoint": "/retentions",
        "columnas": [
            ("nombre", "text", "name"),
            ("porcentaje", "numeric", "percentage"),
            ("tipo", "text", "type"),
            ("tipo_retencion_606", "text", "retentionType606"),
            ("calculado_por", "text", "calculatedBy"),
            ("descripcion", "text", "description"),
            ("estado", "text", "status"),
        ],
    },
    "terms": {
        "tabla": "terminos_pago", "endpoint": "/terms",
        "columnas": [
            ("nombre", "text", "name"),
            ("dias", "numeric", "days"),
            ("estado", "text", "status"),
        ],
    },
    "currencies": {
        "tabla": "monedas", "endpoint": "/currencies", "pk_campo": "code",
        "columnas": [
            ("nombre", "text", "name"),
            ("simbolo", "text", "symbol"),
            ("tasa_cambio", "numeric", "exchangeRate"),
            ("estado", "text", "status"),
        ],
    },
    "users": {
        "tabla": "usuarios", "endpoint": "/users",
        "columnas": [
            ("nombre", "text", "name"),
            ("apellido", "text", "lastName"),
            ("correo", "text", "email"),
            ("nombre_usuario", "text", "username"),
            ("rol", "jsonb", "role"),
            ("cargo", "text", "position"),
            ("telefono", "text", "phone"),
            ("codigo_telefono", "text", "phoneCode"),
            ("idioma", "text", "language"),
            ("permisos", "jsonb", "permissions"),
            ("estado", "text", "status"),
        ],
    },
    "cost_centers": {
        "tabla": "centros_costo", "endpoint": "/cost-centers",
        "columnas": [
            ("codigo", "text", "code"),
            ("nombre", "text", "name"),
            ("descripcion", "text", "description"),
            ("estado", "text", "status"),
        ],
    },
    "categories": {
        "tabla": "cuentas_contables", "endpoint": "/categories",
        "columnas": [
            ("codigo", "text", "code"),
            ("nombre", "text", "name"),
            ("descripcion", "text", "description"),
            ("tipo", "text", "type"),
            ("naturaleza", "text", "nature"),
            ("uso", "jsonb", "use"),
            ("bloqueada", "boolean", "blocked"),
            ("solo_lectura", "boolean", "readOnly"),
            ("id_global", "text", "idGlobal"),
            ("estado", "text", "status"),
        ],
    },
    "bank_accounts": {
        "tabla": "cuentas_bancarias", "endpoint": "/bank-accounts",
        "columnas": [
            ("nombre", "text", "name"),
            ("numero", "text", "number"),
            ("tipo", "text", "type"),
            ("descripcion", "text", "description"),
            ("saldo_inicial", "numeric", "initialBalance"),
            ("fecha_saldo_inicial", "date", "initialBalanceDate"),
            ("estado", "text", "status"),
        ],
    },
    "company": {
        "tabla": "empresa", "endpoint": "/company", "singular": True,
        "columnas": [
            ("nombre", "text", "name"),
            ("nombre_comercial", "text", "tradeName"),
            ("identificacion", "jsonb", "identification"),
            ("tipo_identificacion", "text", "identificationType"),
            ("correo", "text", "email"),
            ("telefono", "text", "phone"),
            ("direccion", "jsonb", "address"),
            ("sitio_web", "text", "website"),
            ("moneda", "jsonb", "currency"),
            ("zona_horaria", "text", "timezone"),
            ("regimen", "text", "regime"),
            ("sector", "text", "sector"),
            ("numero_empleados", "numeric", "employeesNumber"),
            ("configuracion", "jsonb", "settings"),
        ],
    },

    # ---- maestros ----
    "contacts": {
        "tabla": "contactos", "endpoint": "/contacts",
        "columnas": [
            ("nombre", "text", "name"),
            ("tipo", "jsonb", "type"),
            ("estado", "text", "status"),
            ("correo", "text", "email"),
            ("telefono_principal", "text", "phonePrimary"),
            ("telefono_secundario", "text", "phoneSecondary"),
            ("celular", "text", "mobile"),
            ("direccion", "jsonb", "address"),
            ("identificacion", "jsonb", "identificationObject"),
            ("limite_credito", "numeric", "creditLimit"),
            ("lista_precio_id", "text", "priceList.id"),
            ("vendedor_id", "text", "seller.id"),
            ("termino_pago_id", "text", "term.id"),
            ("fecha_creacion", "timestamptz", "created_at"),
            ("fecha_actualizacion", "timestamptz", "updated_at"),
            ("uuid", "text", "uuid"),
        ],
    },
    "items": {
        "tabla": "productos", "endpoint": "/items",
        "columnas": [
            ("nombre", "text", "name"),
            ("descripcion", "text", "description"),
            ("referencia", "jsonb", "reference"),
            ("tipo", "text", "type"),
            ("tipo_item", "text", "itemType"),
            ("estado", "text", "status"),
            ("categoria_id", "text", "itemCategory.id"),
            ("precio", "jsonb", "price"),
            ("inventario", "jsonb", "inventory"),
            ("impuestos", "jsonb", "tax"),
            ("subitems", "jsonb", "subitems"),
        ],
    },

    # ---- transaccionales ----
    "inventory_adjustments": {
        "tabla": "ajustes_inventario", "endpoint": "/inventory-adjustments",
        "columnas": [
            ("fecha", "date", "date"),
            ("numero", "text", "number"),
            ("prefijo", "text", "prefix"),
            ("bodega_id", "text", "warehouse.id"),
            ("centro_costo_id", "text", "costCenter.id"),
            ("items", "jsonb", "items"),
            ("total_costo", "numeric", "totalCostOnlyAdjustment"),
        ],
    },
    "invoices": {
        "tabla": "facturas_venta", "endpoint": "/invoices",
        "columnas": [
            ("numero", "text", "numberTemplate.fullNumber"),
            ("plantilla_numeracion_id", "text", "numberTemplate.id"),
            ("cliente_id", "text", "client.id"),
            ("fecha", "date", "date"),
            ("fecha_vencimiento", "date", "dueDate"),
            ("estado", "text", "status"),
            ("subtotal", "numeric", "subtotal"),
            ("subtotal_con_descuento", "numeric", "subtotalWithDiscount"),
            ("descuento", "jsonb", "discount"),
            ("impuesto", "jsonb", "tax"),
            ("total", "numeric", "total"),
            ("total_pagado", "numeric", "totalPaid"),
            ("saldo", "numeric", "balance"),
            ("metodo_pago", "text", "paymentMethod"),
            ("tipo_pago", "text", "paymentType"),
            ("tipo_ingreso", "text", "incomeType"),
            ("vendedor_id", "text", "seller.id"),
            ("bodega_id", "text", "warehouse.id"),
            ("centro_costo_id", "text", "costCenter.id"),
            ("lista_precio_id", "text", "priceList.id"),
            ("termino_pago_id", "text", "term.id"),
            ("observaciones", "text", "observations"),
            ("items", "jsonb", "items"),
            ("pagos_aplicados", "jsonb", "payments"),
        ],
    },
    "estimates": {
        "tabla": "cotizaciones", "endpoint": "/estimates",
        "columnas": [
            ("numero", "text", "number"),
            ("plantilla_numeracion_id", "text", "numberTemplate.id"),
            ("cliente_id", "text", "client.id"),
            ("fecha", "date", "date"),
            ("fecha_vencimiento", "date", "dueDate"),
            ("estado", "text", "status"),
            ("moneda", "jsonb", "currency"),
            ("total", "numeric", "total"),
            ("vendedor_id", "text", "seller.id"),
            ("bodega_id", "text", "warehouse.id"),
            ("centro_costo_id", "text", "costCenter.id"),
            ("lista_precio_id", "text", "priceList.id"),
            ("observaciones", "text", "anotation"),
            ("items", "jsonb", "items"),
        ],
    },
    "remissions": {
        "tabla": "remisiones", "endpoint": "/remissions",
        "columnas": [
            ("numero", "text", "number"),
            ("plantilla_numeracion_id", "text", "numberTemplate.id"),
            ("cliente_id", "text", "client.id"),
            ("fecha", "date", "date"),
            ("fecha_vencimiento", "date", "dueDate"),
            ("estado", "text", "status"),
            ("total", "numeric", "total"),
            ("vendedor_id", "text", "seller.id"),
            ("bodega_id", "text", "warehouse.id"),
            ("centro_costo_id", "text", "costCenter.id"),
            ("cotizacion_id", "text", "idEstimate"),
            ("observaciones", "text", "anotation"),
            ("items", "jsonb", "items"),
        ],
    },
    "credit_notes": {
        "tabla": "notas_credito", "endpoint": "/credit-notes",
        "columnas": [
            ("cliente_id", "text", "client.id"),
            ("fecha", "date", "date"),
            ("estado", "text", "status"),
            ("subtotal", "numeric", "subtotal"),
            ("descuento", "jsonb", "discount"),
            ("impuesto", "jsonb", "tax"),
            ("total", "numeric", "total"),
            ("total_aplicado", "numeric", "totalApplied"),
            ("facturas_relacionadas", "jsonb", "invoices"),
            ("bodega_id", "text", "warehouse.id"),
            ("centro_costo_id", "text", "costCenter.id"),
            ("observaciones", "text", "anotation"),
            ("items", "jsonb", "items"),
        ],
    },
    "debit_notes": {
        "tabla": "notas_debito", "endpoint": "/debit-notes",
        "columnas": [
            ("cliente_id", "text", "client.id"),
            ("fecha", "date", "date"),
            ("estado_emision", "text", "emissionStatus"),
            ("tipo", "text", "type"),
            ("total", "numeric", "total"),
            ("saldo", "numeric", "balance"),
            ("total_aplicado", "numeric", "totalApplied"),
            ("facturas_compra_relacionadas", "jsonb", "bills"),
            ("categorias", "jsonb", "categories"),
            ("bodega_id", "text", "warehouse.id"),
            ("centro_costo_id", "text", "costCenter.id"),
            ("observaciones", "text", "observations"),
        ],
    },
    "bills": {
        "tabla": "facturas_compra", "endpoint": "/bills",
        "columnas": [
            ("proveedor_id", "text", "provider.id"),
            ("fecha", "date", "date"),
            ("fecha_vencimiento", "date", "dueDate"),
            ("estado", "text", "status"),
            ("total", "numeric", "total"),
            ("total_pagado", "numeric", "totalPaid"),
            ("saldo", "numeric", "balance"),
            ("compras", "jsonb", "purchases"),
            ("retenciones", "jsonb", "retentions"),
            ("pagos_aplicados", "jsonb", "payments"),
            ("bodega_id", "text", "warehouse.id"),
            ("centro_costo_id", "text", "costCenter.id"),
            ("sujeta_proporcionalidad", "boolean", "subjectToProportionality"),
            ("observaciones", "text", "observations"),
        ],
    },
    "purchase_orders": {
        "tabla": "ordenes_compra", "endpoint": "/purchase-orders",
        "columnas": [
            ("proveedor_id", "text", "provider.id"),
            ("fecha", "date", "date"),
            ("fecha_entrega", "date", "deliveryDate"),
            ("estado", "text", "status"),
            ("subtotal", "numeric", "subTotal"),
            ("total", "numeric", "total"),
            ("compras", "jsonb", "purchases"),
            ("bodega_id", "text", "warehouse.id"),
            ("centro_costo_id", "text", "costCenter.id"),
            ("observaciones", "text", "anotation"),
        ],
    },
    "payments": {
        "tabla": "pagos", "endpoint": "/payments",
        "columnas": [
            ("tipo", "text", "type"),
            ("fecha", "date", "date"),
            ("monto", "numeric", "amount"),
            ("estado", "text", "status"),
            ("metodo_pago", "text", "paymentMethod"),
            ("cliente_id", "text", "client.id"),
            ("cuenta_bancaria_id", "text", "bankAccount.id"),
            ("numero", "text", "number"),
            ("plantilla_numeracion_id", "text", "numberTemplate.id"),
            ("centro_costo_id", "text", "costCenter.id"),
            ("facturas_compra_aplicadas", "jsonb", "bills"),
            ("observaciones", "text", "anotation"),
        ],
    },
    "recurring_payments": {
        "tabla": "pagos_recurrentes", "endpoint": "/recurring-payments",
        "columnas": [
            ("cliente_id", "text", "client.id"),
            ("cuenta_id", "text", "account.id"),
            ("monto", "numeric", "amount"),
            ("fecha_inicio", "date", "startDate"),
            ("fecha_fin", "date", "endDate"),
            ("repetir_cada", "jsonb", "repeatEvery"),
            ("fechas_editables", "boolean", "datesEditable"),
            ("plantilla_numeracion_id", "text", "numberTemplate.id"),
        ],
    },
    "journals": {
        "tabla": "comprobantes_contables", "endpoint": "/journals",
        "columnas": [
            ("fecha", "date", "date"),
            ("referencia", "text", "reference"),
            ("cliente_id", "text", "client.id"),
            ("total", "numeric", "total"),
            ("estado", "text", "status"),
            ("observaciones", "text", "observations"),
            ("asientos", "jsonb", "entries"),
        ],
    },
}


def extraer_valor(record, tipo, ruta):
    valor = g(record, ruta)
    if tipo == "jsonb":
        return Json(valor) if valor is not None else None
    if tipo == "numeric":
        try:
            return float(valor) if valor not in (None, "") else None
        except (TypeError, ValueError):
            return None
    if tipo == "boolean":
        if valor is None:
            return None
        if isinstance(valor, bool):
            return valor
        if isinstance(valor, str):
            return valor.lower() in ("true", "1", "yes", "si")
        return bool(valor)
    return valor  # text, date, timestamptz -> psycopg2 los castea bien como string


def ensure_table(cur, tabla, columnas):
    cols_sql = ",\n            ".join(
        f'"{nombre}" {tipo}' for nombre, tipo, _ in columnas
    )
    cur.execute(f"""
        create table if not exists {SCHEMA}."{tabla}" (
            id text primary key,
            {cols_sql},
            datos_originales jsonb,
            sincronizado_en timestamptz not null default now()
        );
    """)


def fetch_page(endpoint, start, singular=False):
    params = {} if singular else {"start": start, "limit": PAGE_SIZE}
    resp = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params=params, timeout=60)

    remaining = resp.headers.get("X-Rate-Limit-Remaining")
    reset = resp.headers.get("X-Rate-Limit-Reset")

    if resp.status_code == 429:
        wait = int(reset) + 1 if reset else 60
        print(f"    rate limit alcanzado, esperando {wait}s...")
        time.sleep(wait)
        return fetch_page(endpoint, start, singular)

    resp.raise_for_status()

    if remaining is not None and int(remaining) <= 3:
        wait = int(reset) + 1 if reset else 5
        time.sleep(wait)

    body = resp.json()

    if singular:
        return [body] if isinstance(body, dict) else []
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        if "data" in body:
            return body["data"]
        if "results" in body:
            return body["results"]
    return []


def cargar_pagina(cur, tabla, columnas, page, pk_campo, forzar_id=None):
    nombres = ["id"] + [c[0] for c in columnas] + ["datos_originales"]
    filas = []
    for record in page:
        pk = forzar_id if forzar_id else record.get(pk_campo)
        if pk is None:
            continue
        valores = [str(pk)]
        for nombre, tipo, ruta in columnas:
            valores.append(extraer_valor(record, tipo, ruta))
        valores.append(Json(record))
        filas.append(tuple(valores))

    if not filas:
        return 0

    columnas_sql = ", ".join(f'"{c}"' for c in nombres)
    set_sql = ", ".join(f'"{c}" = excluded."{c}"' for c in nombres if c != "id")
    placeholders = "(" + ", ".join(["%s"] * len(nombres)) + ", now())"

    execute_values(
        cur,
        f"""
        insert into {SCHEMA}."{tabla}" ({columnas_sql}, sincronizado_en)
        values %s
        on conflict (id) do update set {set_sql}, sincronizado_en = now()
        """,
        filas,
        template=placeholders,
    )
    return len(filas)


def backfill_tabla(cur, conf):
    tabla = conf["tabla"]
    endpoint = conf["endpoint"]
    columnas = conf["columnas"]
    pk_campo = conf.get("pk_campo", "id")
    singular = conf.get("singular", False)

    ensure_table(cur, tabla, columnas)

    if singular:
        page = fetch_page(endpoint, 0, singular=True)
        return cargar_pagina(cur, tabla, columnas, page, pk_campo, forzar_id="1")

    total_synced = 0
    start = 0
    while True:
        page = fetch_page(endpoint, start)
        if not page:
            break
        total_synced += cargar_pagina(cur, tabla, columnas, page, pk_campo)
        start += PAGE_SIZE
        if len(page) < PAGE_SIZE:
            break
    return total_synced


def main():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute(f"create schema if not exists {SCHEMA};")
    conn.commit()

    print(f"Cargando {len(TABLES)} tablas en el schema '{SCHEMA}'...\n")
    for clave, conf in TABLES.items():
        print(f"-> {conf['tabla']:25s}", end=" ", flush=True)
        try:
            n = backfill_tabla(cur, conf)
            conn.commit()
            print(f"OK ({n} registros)")
        except Exception as e:
            conn.rollback()
            print(f"ERROR: {e}")

    cur.close()
    conn.close()
    print("\nListo. Revisa el schema 'alegra' en Supabase.")


if __name__ == "__main__":
    main()