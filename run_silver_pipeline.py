"""
MASTER PIPELINE - Silver Layer ETL
Ejecuta toda la cadena: create_silver_v2 → extract_jsonb → extract_impuestos
"""
import os
import sys
import subprocess
from datetime import datetime

SCRIPTS = [
    ("Alegra_supabase.PY",          "Extrayendo datos desde API Alegra → Bronce"),
    ("create_silver_v2.py",         "Creando schema Silver v2"),
    ("extract_jsonb_to_flat.py",    "Extrayendo JSONB a tablas planas"),
    ("extract_impuestos_to_flat.py","Extrayendo impuestos JSONB"),
]

def main():
    print("=" * 60)
    print(f"PIPELINE SILVER - {datetime.now()}")
    print("=" * 60)

    if not os.environ.get("SUPABASE_DB_URL"):
        print("ERROR: Variable SUPABASE_DB_URL no definida")
        sys.exit(1)

    errors = []
    for script, label in SCRIPTS:
        print(f"\n>>> {label} ({script})...")
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True, text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"ERROR en {script}:")
            print(result.stderr)
            errors.append(script)
        else:
            print(f"OK - {script} completado")

    print("\n" + "=" * 60)
    if errors:
        print(f"PIPELINE COMPLETADO CON {len(errors)} ERROR(ES): {errors}")
        sys.exit(1)
    else:
        print("PIPELINE COMPLETADO EXITOSAMENTE")
    print("=" * 60)

if __name__ == "__main__":
    main()
