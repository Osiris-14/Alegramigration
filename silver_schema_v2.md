# Reporte de Construcción — Schema SILVER
### Proyecto: Alegra Data Migration
**Fecha:** 2026-07-06  
**Base de datos:** Supabase (aws-1-us-east-1) — proyecto `xilcckvfaawcmjeazhku`

---

## Resumen Ejecutivo

Se construyó la capa **SILVER** de la arquitectura Medallion sobre Supabase.
Esta capa toma los datos crudos del schema `alegra` (Bronze), aplica limpieza,
normalización y tipificación, y los expone con relaciones referenciales completas
para su uso en análisis, BI y capas Gold. Todos los JSONB originales fueron
extraídos a tablas planas.

| Métrica | Valor |
|---|---|
| Tablas creadas | **28** |
| Filas totales | **210,628** |
| Foreign Keys | **36** |
| Índices adicionales | **28** |
| Columnas JSONB eliminadas | **17** |
| Orphans resueltos (NULL) | 13,787 registros |

---

## Arquitectura del Schema SILVER

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SCHEMA: silver                              │
│                                                                     │
│  CATÁLOGOS (lookup tables)                                          │
│  ┌──────────────────┐  ┌─────────────┐  ┌───────────────┐          │
│  │ categorias_prod. │  │   bodegas   │  │ centros_costo │          │
│  │     46 filas     │  │   3 filas   │  │    7 filas    │          │
│  └──────────────────┘  └─────────────┘  └───────────────┘          │
│  ┌──────────────┐  ┌────────────────┐  ┌──────────────────┐        │
│  │   impuestos  │  │ terminos_pago  │  │   retenciones    │        │
│  │    6 filas   │  │    5 filas     │  │    13 filas      │        │
│  └──────────────┘  └────────────────┘  └──────────────────┘        │
│  ┌────────────────────┐                                             │
│  │  cuentas_bancarias │                                             │
│  │      14 filas      │                                             │
│  └────────────────────┘                                             │
│                                                                     │
│  ENTIDADES MAESTRAS                                                 │
│  ┌─────────────────────┐       ┌─────────────────────┐             │
│  │      contactos      │       │      usuarios       │             │
│  │     25,933 filas    │       │       9 filas       │             │
│  └─────────────────────┘       └─────────────────────┘             │
│  ┌─────────────────────┐                                           │
│  │      productos      │──┐                                        │
│  │      1,539 filas    │  │  ┌────────────────────────┐            │
│  └─────────────────────┘  ├──│ productos_impuestos    │ 57 filas   │
│                           │  └────────────────────────┘            │
│                           │  ┌────────────────────────┐            │
│                           └──│ productos_subitems     │ 77 filas   │
│                              └────────────────────────┘            │
│                                                                     │
│  DOCUMENTOS DE VENTA                                               │
│  ┌─────────────────┐  ┌──────────────────────┐                     │
│  │  cotizaciones   │  │   facturas_venta     │                     │
│  │   26,587 filas  │  │     3,403 filas      │                     │
│  └────┬────────────┘  └─────┬────────────────┘                     │
│       │                     │                                      │
│       │  ┌──────────────────┐│  ┌─────────────────────────┐        │
│       ├──│ cotizaciones_    │├──│ facturas_venta_items   │8,527    │
│       │  │ items (72,542)   ││  └─────────────────────────┘        │
│       │  └──────────────────┘│  ┌──────────────────────────┐       │
│       │                     ├──│ facturas_venta_pagos_    │5,503   │
│       │                     │  │ aplicados                │        │
│       │                     │  └──────────────────────────┘        │
│  ┌──────────────────┐  ┌────┴──────────────┐                       │
│  │  notas_credito   │  │  notas_debito     │                       │
│  │     15 filas     │  │    36 filas       │                       │
│  └────┬─────────────┘  └───────────────────┘                       │
│       │                                                           │
│       │  ┌─────────────────────────────┐                          │
│       ├──│ notas_credito_items (24)    │                          │
│       │  └─────────────────────────────┘                          │
│       │  ┌──────────────────────────────────────────┐             │
│       └──│ notas_credito_facturas_relacionadas (12) │             │
│          └──────────────────────────────────────────┘             │
│                                                                     │
│  DOCUMENTOS DE COMPRA                                             │
│  ┌──────────────────┐  ┌────────────────────┐                      │
│  │ facturas_compra  │  │  ordenes_compra    │                      │
│  │   2,432 filas    │  │    754 filas       │                      │
│  └─────┬────────────┘  └─────┬──────────────┘                      │
│        │                     │                                     │
│        │  ┌──────────────────┐│  ┌──────────────────────────┐      │
│        ├──│ facturas_compra_ ├──│ ordenes_compra_compras    │      │
│        │  │ compras (9,698)  │  │ (4,695)                   │      │
│        │  └──────────────────┘  └──────────────────────────┘      │
│        │  ┌──────────────────────────┐                             │
│        ├──│ facturas_compra_pagos_  │ 3,056                       │
│        │  │ aplicados               │                             │
│        │  └──────────────────────────┘                             │
│                                                                     │
│  PAGOS                                                             │
│  ┌───────────────────────┐                                         │
│  │         pagos         │──┐                                      │
│  │      29,337 filas     │  │  ┌─────────────────────────┐        │
│  └───────────────────────┘  └──│ pagos_facturas_aplicadas│3,062    │
│                               └─────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Detalle de Tablas

### Tablas Mejoradas (existían en v1, enriquecidas en v2)

#### `silver.contactos` — 25,933 filas
| Columna | Tipo | Descripción |
|---|---|---|
| `alegra_id` | text PK | ID original de Alegra |
| `nombre` | text | Nombre sin espacios (`trim`) |
| `rnc` | text | RNC/Cédula; `'0000000'` si vacío |
| `tipo_identificacion` | text | Tipo de documento |
| `es_cliente` | boolean | `true` si tipo contiene 'client' |
| `es_proveedor` | boolean | `true` si tipo contiene 'provider' |
| `email` | text | Correo |
| `telefono` | text | Solo 10 dígitos, prefijo +1 eliminado |
| `dir_descripcion` | text | Extraído de JSON `direccion` |
| `dir_municipio` | text | Extraído de JSON `direccion` |
| `dir_provincia` | text | Extraído de JSON `direccion` |
| `dir_pais` | text | Extraído de JSON `direccion` |
| `limite_credito` | numeric | Límite de crédito |
| `lista_precio_id` | text | Lista de precios asignada |
| `vendedor_id` | text FK→usuarios | Vendedor asignado |
| `termino_pago_id` | text FK→terminos_pago | Términos de pago |
| `uuid` | text | UUID externo de Alegra |
| `fecha_creacion` | timestamptz | Fecha de alta en Alegra |
| `fecha_actualizacion` | timestamptz | Última modificación |
| `estado` | text | Estado del contacto |
| `alegra_sync_at` | timestamptz | Timestamp de sincronización |

**Estadísticas:**
- Clientes: 24,913 (96.1%)
- Proveedores: 67 (0.3%)
- Sin RNC (placeholder '0000000'): 24,751 (95.4%)
- Con municipio: 190
- Con límite de crédito: 150

---

#### `silver.productos` — 1,539 filas
| Columna | Tipo | Descripción |
|---|---|---|
| `alegra_id` | text PK | ID original |
| `nombre` | text | Truncado a 80 chars + trim |
| `descripcion` | text | Descripción larga |
| `tipo` | text | Tipo de producto |
| `tipo_item` | text | Subtipo |
| `estado` | text | Estado |
| `referencia` | text | Extraído del JSON `referencia->>'reference'` |
| `precio_1` | numeric | Precio principal (`main=true`), 0 si no existe |
| `precio_2` | numeric | Precio secundario (`main=false`) |
| `costo` | numeric | Costo unitario del inventario |
| `stock_disponible` | numeric | Cantidad disponible |
| `unidad` | text | Unidad de medida |
| `tiene_itbis` | boolean | `true` si algún impuesto es tipo ITBIS |
| `categoria_id` | text FK→categorias_productos | Categoría |
| `alegra_sync_at` | timestamptz | Timestamp de sincronización |

**Tablas hijas planas:**
- `silver.productos_impuestos` (57 filas) — Impuestos por producto
- `silver.productos_subitems` (77 filas) — Componentes de productos compuestos

---

#### `silver.facturas_venta` — 3,403 filas
| Columna | Tipo | Descripción |
|---|---|---|
| `alegra_id` | text PK | ID original |
| `ncf` | text | Número de comprobante fiscal |
| `cliente_alegra_id` | text FK→contactos | Cliente |
| `vendedor_alegra_id` | text FK→usuarios | Vendedor |
| `fecha` | date | Fecha de emisión |
| `fecha_vencimiento` | date | Fecha de vencimiento |
| `estado` | text | open / closed / void |
| `subtotal` | numeric | Subtotal bruto |
| `subtotal_con_descuento` | numeric | Subtotal post-descuento |
| `descuento_monto` | numeric | Monto del descuento |
| `impuesto_monto` | numeric | Monto de impuesto |
| `total` | numeric | Total de la factura |
| `total_pagado` | numeric | Monto pagado |
| `saldo` | numeric | Saldo pendiente |
| `metodo_pago` | text | Método de pago |
| `tipo_pago` | text | Tipo de pago |
| `tipo_ingreso` | text | Tipo de ingreso |
| `bodega_id` | text FK→bodegas | Bodega |
| `centro_costo_id` | text FK→centros_costo | Centro de costo |
| `lista_precio_id` | text | Lista de precios |
| `termino_pago_id` | text FK→terminos_pago | Términos de pago |
| `plantilla_numeracion_id` | text | Plantilla NCF |
| `observaciones` | text | Notas |
| `num_items` | integer | Cantidad de ítems |
| `alegra_sync_at` | timestamptz | Timestamp de sincronización |

**Tablas hijas planas:**
- `silver.facturas_venta_items` (8,527 filas) — Líneas de detalle de cada factura
- `silver.facturas_venta_pagos_aplicados` (5,503 filas) — Pagos vinculados a cada factura

**Estadísticas:**
- closed: 2,661 | RD$ 83,017,491.75
- open: 667 | RD$ 24,698,118.64
- void: 75 | RD$ 2,311,164.80
- **TOTAL: RD$ 110,026,775.19**

---

#### `silver.usuarios` — 9 filas
| Columna | Tipo | Descripción |
|---|---|---|
| `alegra_id` | text PK | ID original |
| `nombre` | text | Nombre con trim |
| `apellido` | text | Apellido con trim |
| `nombre_completo` | text | Concatenación nombre + apellido |
| `email` | text | Correo |
| `nombre_usuario` | text | Username en Alegra |
| `rol` | text | Rol extraído del JSON (admin/user/etc.) |
| `cargo` | text | Cargo en la empresa |
| `telefono` | text | Solo dígitos |
| `codigo_telefono` | text | Código de país |
| `idioma` | text | Idioma configurado |
| `estado` | text | Estado del usuario |
| `alegra_sync_at` | timestamptz | Timestamp de sincronización |

---

### Tablas Nuevas — Documentos de Venta

#### `silver.cotizaciones` — 26,587 filas
| Columna | Tipo | Descripción |
|---|---|---|
| `alegra_id` | text PK | ID original |
| `numero` | text | Número de cotización |
| `cliente_alegra_id` | text FK→contactos | Cliente |
| `vendedor_alegra_id` | text FK→usuarios | Vendedor |
| `fecha` | date | Fecha |
| `fecha_vencimiento` | date | Vencimiento |
| `estado` | text | open / unbilled / billed |
| `moneda_codigo` | text | Código moneda (DOP, USD) |
| `moneda_simbolo` | text | Símbolo |
| `tasa_cambio` | numeric | Tasa de cambio |
| `total` | numeric | Total cotizado |
| `bodega_id` | text FK→bodegas | Bodega |
| `centro_costo_id` | text FK→centros_costo | Centro de costo |
| `lista_precio_id` | text | Lista de precios |
| `plantilla_numeracion_id` | text | Plantilla |
| `observaciones` | text | Notas |
| `num_items` | integer | Cantidad de ítems |
| `alegra_sync_at` | timestamptz | Timestamp de sincronización |

**Tabla hija plana:**
- `silver.cotizaciones_items` (72,542 filas) — Líneas de detalle de cada cotización

**Estadísticas:**
- unbilled: 12,032 | RD$ 466,223,200.42
- open: 11,374 | RD$ 375,164,601.14
- billed: 3,181 | RD$ 103,497,056.07
- **PIPELINE TOTAL: RD$ 944,884,857.63**

---

#### `silver.notas_credito` — 15 filas
Devoluciones aplicadas a clientes. Columnas: `alegra_id`, `cliente_alegra_id` FK, `fecha`, `estado`, `subtotal`, `descuento_monto`, `impuesto_monto`, `total`, `total_aplicado`, `bodega_id` FK, `centro_costo_id`, `observaciones`.

**Tablas hijas planas:**
- `silver.notas_credito_items` (24 filas) — Líneas de detalle
- `silver.notas_credito_facturas_relacionadas` (12 filas) — Facturas vinculadas a la nota de crédito

#### `silver.notas_debito` — 36 filas
Cargos adicionales a clientes. Columnas: `alegra_id`, `cliente_alegra_id` FK, `fecha`, `tipo`, `estado`, `total`, `saldo`, `total_aplicado`, `bodega_id` FK, `centro_costo_id`, `observaciones`.

---

### Tablas Nuevas — Documentos de Compra

#### `silver.facturas_compra` — 2,432 filas
| Columna | Tipo |
|---|---|
| `alegra_id` | text PK |
| `proveedor_alegra_id` | text FK→contactos |
| `fecha` / `fecha_vencimiento` | date |
| `estado` | text |
| `total` / `total_pagado` / `saldo` | numeric |
| `bodega_id` | text FK→bodegas |
| `centro_costo_id` | text FK→centros_costo |
| `sujeta_proporcionalidad` | boolean |
| `observaciones` | text |
| `num_items` | integer |

**Tablas hijas planas:**
- `silver.facturas_compra_compras` (9,698 filas) — Productos/servicios comprados
- `silver.facturas_compra_pagos_aplicados` (3,056 filas) — Pagos vinculados

**Relación referencial (sin datos actuales):**
- `silver.retenciones` — Catálogo de 13 tipos de retenciones (ITBIS, Fuente, etc.). Ninguna factura de compra actual tiene retenciones aplicadas, pero el catálogo está disponible para uso futuro.

#### `silver.ordenes_compra` — 754 filas
Columnas: `alegra_id`, `proveedor_alegra_id` FK, `fecha`, `fecha_entrega`, `estado`, `subtotal`, `total`, `bodega_id` FK, `centro_costo_id` FK, `observaciones`, `num_items`.

**Tabla hija plana:**
- `silver.ordenes_compra_compras` (4,695 filas) — Productos/servicios ordenados

---

### Tablas Nuevas — Pagos

#### `silver.pagos` — 29,337 filas
| Columna | Tipo | Descripción |
|---|---|---|
| `alegra_id` | text PK | ID original |
| `numero` | text | Número de pago |
| `tipo` | text | `in` = cobro a cliente / `out` = pago a proveedor |
| `fecha` | date | Fecha del pago |
| `monto` | numeric | Monto |
| `estado` | text | Estado |
| `metodo_pago` | text | cash / transfer / check / etc. |
| `contacto_alegra_id` | text FK→contactos | Cliente o proveedor |
| `cuenta_bancaria_id` | text FK→cuentas_bancarias | Cuenta bancaria |
| `centro_costo_id` | text FK→centros_costo | Centro de costo |
| `plantilla_numeracion_id` | text | Plantilla |
| `observaciones` | text | Notas |
| `alegra_sync_at` | timestamptz | Timestamp de sincronización |

**Tabla hija plana:**
- `silver.pagos_facturas_aplicadas` (3,062 filas) — Facturas que cancela cada pago

**Estadísticas:**
- Pagos entrantes (cobros): 7,430 | RD$ 171,076,627.75
- Pagos salientes (proveedores): 21,907 | RD$ 164,473,067.38
- **FLUJO TOTAL: RD$ 335,549,695.13**

---

### Tablas Planas — Items, Pagos e Impuestos

#### Items de Documentos

| Tabla | Filas | Documento padre | Columnas principales |
|---|---|---|---|
| `silver.facturas_venta_items` | 8,527 | facturas_venta | `factura_alegra_id`, `linea`, `item_id`, `nombre`, `unidad`, `referencia`, `tipo_item`, `descripcion`, `cantidad`, `precio_unitario`, `descuento_porcentaje`, `descuento_monto`, `total`, `tipo_descuento` |
| `silver.cotizaciones_items` | 72,542 | cotizaciones | `cotizacion_alegra_id`, `linea`, `item_id`, `nombre`, `referencia`, `descripcion`, `cantidad`, `precio_unitario`, `descuento_porcentaje`, `total` |
| `silver.notas_credito_items` | 24 | notas_credito | `nota_credito_alegra_id`, `linea`, `item_id`, `nombre`, `referencia`, `descripcion`, `cantidad`, `precio_unitario`, `descuento_porcentaje`, `subtotal`, `total` |
| `silver.facturas_compra_compras` | 9,698 | facturas_compra | `factura_compra_alegra_id`, `linea`, `item_id`, `nombre`, `cantidad`, `precio_unitario`, `descuento`, `subtotal`, `monto_impuesto`, `total`, `observaciones` |
| `silver.ordenes_compra_compras` | 4,695 | ordenes_compra | `orden_compra_alegra_id`, `linea`, `item_id`, `nombre`, `cantidad`, `precio_unitario`, `descuento`, `total`, `observaciones` |

#### Pagos Aplicados y Facturas Relacionadas

| Tabla | Filas | Documento padre | Columnas principales |
|---|---|---|---|
| `silver.facturas_venta_pagos_aplicados` | 5,503 | facturas_venta | `factura_alegra_id`, `linea`, `pago_id`, `numero_pago`, `prefijo`, `fecha`, `estado`, `monto`, `metodo_pago` |
| `silver.facturas_compra_pagos_aplicados` | 3,056 | facturas_compra | `factura_compra_alegra_id`, `linea`, `pago_id`, `numero_pago`, `prefijo`, `fecha`, `estado`, `monto`, `metodo_pago` |
| `silver.pagos_facturas_aplicadas` | 3,062 | pagos | `pago_alegra_id`, `linea`, `factura_id`, `numero_factura`, `fecha`, `fecha_vencimiento`, `total_factura`, `monto_aplicado` |
| `silver.notas_credito_facturas_relacionadas` | 12 | notas_credito | `nota_credito_alegra_id`, `linea`, `factura_id`, `numero_factura`, `prefijo`, `numero_completo`, `fecha`, `fecha_vencimiento`, `total_factura`, `monto_aplicado`, `saldo` |

#### Impuestos por Item y Subitems

| Tabla | Filas | Tabla padre | Columnas principales |
|---|---|---|---|
| `silver.facturas_venta_items_impuestos` | 1,010 | facturas_venta_items | `factura_alegra_id`, `item_linea`, `impuesto_linea`, `impuesto_id`, `nombre`, `tipo`, `monto`, `porcentaje`, `estado` |
| `silver.cotizaciones_items_impuestos` | 3,803 | cotizaciones_items | `cotizacion_alegra_id`, `item_linea`, `impuesto_linea`, `impuesto_id`, `nombre`, `tipo`, `monto`, `porcentaje`, `estado`, `deducible` |
| `silver.notas_credito_items_impuestos` | 0 | notas_credito_items | `nota_credito_alegra_id`, `item_linea`, `impuesto_linea`, `impuesto_id`, `nombre`, `tipo`, `monto`, `porcentaje`, `estado` |
| `silver.facturas_compra_compras_impuestos` | 8,372 | facturas_compra_compras | `factura_compra_alegra_id`, `item_linea`, `impuesto_linea`, `impuesto_id`, `nombre`, `tipo`, `monto`, `porcentaje`, `estado`, `deducible` |
| `silver.ordenes_compra_compras_impuestos` | 51 | ordenes_compra_compras | `orden_compra_alegra_id`, `item_linea`, `impuesto_linea`, `impuesto_id`, `nombre`, `tipo`, `monto`, `porcentaje`, `estado`, `deducible` |
| `silver.productos_impuestos` | 57 | productos | `producto_alegra_id`, `linea`, `impuesto_id`, `nombre`, `tipo`, `porcentaje`, `estado`, `deducible` |
| `silver.productos_subitems` | 77 | productos | `producto_alegra_id`, `linea`, `cantidad`, `precio`, `subitem_id`, `nombre`, `tipo`, `estado`, `referencia`, `stock_disponible`, `unidad`, `costo_unitario` |

---

### Catálogos de Referencia

| Tabla | Filas | Columnas principales |
|---|---|---|
| `silver.categorias_productos` | 46 | `alegra_id` PK, `nombre`, `descripcion`, `estado` |
| `silver.bodegas` | 3 | `alegra_id` PK, `nombre`, `es_principal`, `centro_costo_id`, `estado` |
| `silver.centros_costo` | 7 | `alegra_id` PK, `codigo`, `nombre`, `descripcion`, `estado` |
| `silver.impuestos` | 6 | `alegra_id` PK, `nombre`, `porcentaje`, `tipo`, `estado` |
| `silver.terminos_pago` | 5 | `alegra_id` PK, `nombre`, `dias`, `estado` |
| `silver.retenciones` | 13 | `alegra_id` PK, `nombre`, `porcentaje`, `tipo`, `tipo_retencion_606`, `calculado_por`. Catalog de tipos de retención (ITBIS, Fuente...) para `facturas_compra` (sin datos actuales) |
| `silver.cuentas_bancarias` | 14 | `alegra_id` PK, `nombre`, `numero`, `tipo`, `saldo_inicial`, `estado` |

---

## Mapa de Foreign Keys (36 constraints)

```
silver.contactos
  ├── .vendedor_id         → silver.usuarios
  └── .termino_pago_id     → silver.terminos_pago

silver.productos
  └── .categoria_id        → silver.categorias_productos

silver.facturas_venta
  ├── .cliente_alegra_id   → silver.contactos
  ├── .vendedor_alegra_id  → silver.usuarios
  ├── .bodega_id           → silver.bodegas
  ├── .centro_costo_id     → silver.centros_costo
  └── .termino_pago_id     → silver.terminos_pago

silver.cotizaciones
  ├── .cliente_alegra_id   → silver.contactos
  ├── .vendedor_alegra_id  → silver.usuarios
  ├── .bodega_id           → silver.bodegas
  └── .centro_costo_id     → silver.centros_costo

silver.pagos
  ├── .contacto_alegra_id  → silver.contactos
  ├── .cuenta_bancaria_id  → silver.cuentas_bancarias
  └── .centro_costo_id     → silver.centros_costo

silver.facturas_compra
  ├── .proveedor_alegra_id → silver.contactos
  ├── .bodega_id           → silver.bodegas
  └── .centro_costo_id     → silver.centros_costo

silver.ordenes_compra
  ├── .proveedor_alegra_id → silver.contactos
  ├── .bodega_id           → silver.bodegas
  └── .centro_costo_id     → silver.centros_costo

silver.notas_credito
  ├── .cliente_alegra_id   → silver.contactos
  └── .bodega_id           → silver.bodegas

silver.notas_debito
  ├── .cliente_alegra_id   → silver.contactos
  └── .bodega_id           → silver.bodegas

--- Referencia (sin FK física actual) ---

silver.facturas_compra
  └── .retenciones (*)     → silver.retenciones (catálogo disponible, sin datos actuales)

--- Tablas Planas (Items, Pagos, Impuestos) ---

silver.facturas_venta_items
  └── .factura_alegra_id   → silver.facturas_venta

silver.facturas_venta_pagos_aplicados
  └── .factura_alegra_id   → silver.facturas_venta

silver.cotizaciones_items
  └── .cotizacion_alegra_id → silver.cotizaciones

silver.notas_credito_items
  └── .nota_credito_alegra_id → silver.notas_credito

silver.notas_credito_facturas_relacionadas
  └── .nota_credito_alegra_id → silver.notas_credito

silver.facturas_compra_compras
  └── .factura_compra_alegra_id → silver.facturas_compra

silver.facturas_compra_pagos_aplicados
  └── .factura_compra_alegra_id → silver.facturas_compra

silver.ordenes_compra_compras
  └── .orden_compra_alegra_id → silver.ordenes_compra

silver.pagos_facturas_aplicadas
  └── .pago_alegra_id     → silver.pagos

silver.productos_impuestos
  └── .producto_alegra_id → silver.productos

silver.productos_subitems
  └── .producto_alegra_id → silver.productos

silver.facturas_venta_items_impuestos
  └── (.factura_alegra_id, .item_linea) → silver.facturas_venta_items

silver.cotizaciones_items_impuestos
  └── (.cotizacion_alegra_id, .item_linea) → silver.cotizaciones_items

silver.notas_credito_items_impuestos
  └── (.nota_credito_alegra_id, .item_linea) → silver.notas_credito_items

silver.facturas_compra_compras_impuestos
  └── (.factura_compra_alegra_id, .item_linea) → silver.facturas_compra_compras

silver.ordenes_compra_compras_impuestos
  └── (.orden_compra_alegra_id, .item_linea) → silver.ordenes_compra_compras
```

> Todos los FKs tienen `ON DELETE CASCADE` y son `DEFERRABLE INITIALLY DEFERRED`.

---

## Observaciones de Calidad de Datos

| Problema | Magnitud | Acción tomada |
|---|---|---|
| Contactos sin RNC/cédula | 24,751 (95.4%) | Placeholder `'0000000'` asignado |
| Cotizaciones sin cliente en Silver | 4,281 | FK → NULL (contactos eliminados en Alegra) |
| Pagos sin cuenta bancaria en Silver | 8,993 | FK → NULL (cuentas históricas eliminadas) |
| Pagos sin contacto en Silver | 509 | FK → NULL |
| Facturas venta sin cliente | 2 | FK → NULL |
| Facturas compra sin proveedor | 1 | FK → NULL |
| Contactos sin vendedor asignado | 1 orphan | FK → NULL |
| Cotizaciones sin vendedor | 3 | FK → NULL |
| Teléfonos con formato inválido | variable | Marcados como NULL |
| Impuesto en facturas = 0 numérico | mayoría | Campo impuesto_monto → NULL |
| JSONB → Tablas planas | 17 columnas | Extraídas a 16 tablas hijas |

> **Nota sobre pagos.cuenta_bancaria_id:** 8,993 pagos quedaron sin cuenta bancaria vinculada.
> Esto se debe a que Alegra solo tiene **14 cuentas bancarias activas**, pero existen pagos
> históricos que referencian cuentas ya eliminadas del sistema. Los datos originales
> siguen disponibles en `alegra.pagos.datos_originales`.

---

## Archivos Generados

| Archivo | Descripción |
|---|---|
| [`create_silver_schema.py`](create_silver_schema.py) | Script v1 original (4 tablas básicas) |
| [`create_silver_v2.py`](create_silver_v2.py) | Script v2 completo (17 tablas mejoradas) |
| [`check_fk_orphans.py`](check_fk_orphans.py) | Diagnóstico de orphans por relación |
| [`add_silver_fks.py`](add_silver_fks.py) | Creación de las 25 FK constraints |
| [`extract_jsonb_to_flat.py`](extract_jsonb_to_flat.py) | Extracción de JSONB a 11 tablas planas |
| [`extract_impuestos_to_flat.py`](extract_impuestos_to_flat.py) | Extracción de impuestos JSONB a 5 tablas |
| [`silver_schema.md`](silver_schema.md) | Documentación técnica v1 |
| `silver_schema_v2.md` | Este archivo — documentación completa |

---

## Comparativa v1 vs v2

| Métrica | Silver v1 | Silver v2 | Silver v2 (post-JSONB) |
|---|---|---|---|
| Tablas | 4 | **17** | **28** |
| Filas totales | ~31,000 | **90,139** | **210,628** |
| Foreign Keys | 0 | **25** | **36** |
| Catálogos | 0 | **7** | **7** |
| Cotizaciones incluidas | ❌ | ✅ 26,587 | ✅ |
| Pagos incluidos | ❌ | ✅ 29,337 | ✅ |
| Facturas de compra | ❌ | ✅ 2,432 | ✅ |
| Dirección de contactos | ❌ | ✅ (4 campos) | ✅ |
| Items de facturas | ❌ | ✅ (JSONB) | ✅ (tablas planas) |
| Pagos aplicados | ❌ | ✅ (JSONB) | ✅ (tablas planas) |
| Impuestos por item | ❌ | ❌ | ✅ (tablas planas) |
| Subitems de productos | ❌ | ✅ (JSONB) | ✅ (tablas planas) |
| Columnas JSONB | 0 | **17** | **0** |
| Columnas por tabla (promedio) | ~10 | ~18 | ~14 |

---

## Cifras Clave del Negocio (extraídas del Silver)

| KPI | Valor |
|---|---|
| Contactos totales | 25,933 |
| Clientes activos | 24,913 |
| Proveedores | 67 |
| Productos/servicios | 1,539 |
| Facturas emitidas | 3,403 |
| Monto facturado total | **RD$ 110,026,775** |
| Pipeline de cotizaciones | **RD$ 944,884,857** |
| Flujo de pagos total | **RD$ 335,549,695** |
| Compras a proveedores | 2,432 facturas |
| Órdenes de compra | 754 |

---

*Generado: 2026-07-06 | Schema: silver | DB: Supabase xilcckvfaawcmjeazhku*
