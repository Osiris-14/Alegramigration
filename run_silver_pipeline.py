"""
MASTER PIPELINE - Silver Layer ETL

Modos:
  python run_silver_pipeline.py              -> full (5 pasos)
  python run_silver_pipeline.py --mode full  -> full (5 pasos)
  python run_silver_pipeline.py --mode incremental -> incremental (1 paso, solo bronce)

Modo FULL  (1 vez/dia, madrugada):
  1. Alegra_supabase.PY              - Backfill completo → bronce (UPSERT por id)
  2. create_silver_v2.py             - Reconstruye schema Silver desde cero
  3. extract_jsonb_to_flat.py        - Aplana JSONBs desde alegra.* a tablas silver.*_items
  4. extract_impuestos_to_flat.py    - Aplana impuestos JSONB
  5. add_silver_fks.py               - Agrega Foreign Keys

Modo INCREMENTAL (cada ~4h, resto del dia):
  1. Alegra_supabase.PY --incremental - UPSERT en bronce, nada mas

  Silver queda "stale" hasta el proximo FULL diario (max 24h de latencia).
  Esto es OK para BI/migracion. Si necesitas silver en tiempo real,
  hay que agregar UPSERT al silver layer (mas complejo).
"""
import os
import sys
import subprocess
from datetime import datetime

# Forzar UTF-8 en stdout/stderr para compatibilidad con Windows cp1252
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Secuencia completa para el sync full
SCRIPTS_FULL = [
    (["Alegra_supabase.PY"],                    "Extrayendo datos desde API Alegra -> Bronce (FULL)"),
    (["create_silver_v2.py"],                   "Creando schema Silver v2"),
    (["extract_jsonb_to_flat.py"],              "Extrayendo JSONB a tablas planas"),
    (["extract_impuestos_to_flat.py"],          "Extrayendo impuestos JSONB"),
    (["add_silver_fks.py"],                     "Agregando Foreign Keys a entidades maestras"),
]

# Incremental: solo bronce. Silver se regenera en el FULL diario.
SCRIPTS_INCREMENTAL = [
    (["Alegra_supabase.PY", "--incremental"],   "Extrayendo datos desde API Alegra -> Bronce (INCREMENTAL)"),
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
            print(f"\n>>> ABORTANDO: {args[0]} falló, los pasos siguientes requieren este paso")
            sys.exit(1)

    print("\n" + "=" * 60)
    print(f"PIPELINE [{mode.upper()}] COMPLETADO EXITOSAMENTE")
    print("=" * 60)


if __name__ == "__main__":
    main()
