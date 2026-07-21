"""
MASTER PIPELINE - Silver Layer ETL

Modos:
  python run_silver_pipeline.py              -> full (5 pasos)
  python run_silver_pipeline.py --mode full  -> full (5 pasos)
  python run_silver_pipeline.py --mode incremental -> incremental (3 pasos)

Modo FULL  (1 vez/dia, madrugada):
  1. Alegra_supabase.PY         - Backfill completo de 27 tablas → bronce
  2. create_silver_v2.py        - Recrea schema Silver (DROP + CREATE AS SELECT)
  3. extract_jsonb_to_flat.py   - Aplana JSONBs
  4. extract_impuestos_to_flat.py - Aplana impuestos
  5. add_silver_fks.py          - Agrega Foreign Keys

Modo INCREMENTAL (cada ~4h, resto del dia):
  1. Alegra_supabase.PY --incremental  - Solo tablas transaccionales desde ultimo sync
  2. extract_jsonb_to_flat.py          - Re-aplana (upsert, no destruye)
  3. extract_impuestos_to_flat.py      - Re-aplana impuestos (upsert)
  NOTA: create_silver_v2 y add_silver_fks usan DROP TABLE CASCADE
        y no son seguros de correr en incremental.
"""
import os
import sys
import subprocess
from datetime import datetime

# Secuencia completa para el sync full
SCRIPTS_FULL = [
    (["Alegra_supabase.PY"],                    "Extrayendo datos desde API Alegra → Bronce (FULL)"),
    (["create_silver_v2.py"],                   "Creando schema Silver v2"),
    (["extract_jsonb_to_flat.py"],              "Extrayendo JSONB a tablas planas"),
    (["extract_impuestos_to_flat.py"],          "Extrayendo impuestos JSONB"),
    (["add_silver_fks.py"],                     "Agregando Foreign Keys a entidades maestras"),
]

# Solo los pasos seguros para el sync incremental
SCRIPTS_INCREMENTAL = [
    (["Alegra_supabase.PY", "--incremental"],   "Extrayendo datos desde API Alegra → Bronce (INCREMENTAL)"),
    (["extract_jsonb_to_flat.py"],              "Extrayendo JSONB a tablas planas"),
    (["extract_impuestos_to_flat.py"],          "Extrayendo impuestos JSONB"),
]


def run_script(args, label):
    print(f"\n>>> {label} ({args[0]})...")
    result = subprocess.run(
        [sys.executable] + args,
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"ERROR en {args[0]}:")
        print(result.stderr)
        return False
    print(f"OK - {args[0]} completado")
    return True


def main():
    # Detectar modo desde argumentos
    mode = "full"
    if "--mode" in sys.argv:
        idx = sys.argv.index("--mode")
        if idx + 1 < len(sys.argv):
            mode = sys.argv[idx + 1].lower()

    if mode not in ("full", "incremental"):
        print(f"ERROR: --mode debe ser 'full' o 'incremental', se recibio: {mode}")
        sys.exit(1)

    print("=" * 60)
    print(f"PIPELINE SILVER [{mode.upper()}] - {datetime.now()}")
    print("=" * 60)

    if not os.environ.get("SUPABASE_DB_URL"):
        print("ERROR: Variable SUPABASE_DB_URL no definida")
        sys.exit(1)

    scripts = SCRIPTS_FULL if mode == "full" else SCRIPTS_INCREMENTAL
    errors = []

    for args, label in scripts:
        ok = run_script(args, label)
        if not ok:
            errors.append(args[0])

    print("\n" + "=" * 60)
    if errors:
        print(f"PIPELINE [{mode.upper()}] COMPLETADO CON {len(errors)} ERROR(ES): {errors}")
        sys.exit(1)
    else:
        print(f"PIPELINE [{mode.upper()}] COMPLETADO EXITOSAMENTE")
    print("=" * 60)


if __name__ == "__main__":
    main()
