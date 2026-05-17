"""Diagnose sgpt import block"""
import sys, traceback
sys.stdout.reconfigure(line_buffering=True)
print("STEP 0: starting", flush=True)

try:
    import readline
    print("STEP 1: readline OK", flush=True)
except Exception as e:
    print(f"STEP 1 FAIL: {e}", flush=True)

try:
    from prompt_toolkit import PromptSession
    print("STEP 2: prompt_toolkit OK", flush=True)
except Exception as e:
    print(f"STEP 2 FAIL: {e}", flush=True)

try:
    import typer
    print("STEP 3: typer OK", flush=True)
except Exception as e:
    print(f"STEP 3 FAIL: {e}", flush=True)

try:
    from click.types import Choice
    print("STEP 4: click OK", flush=True)
except Exception as e:
    print(f"STEP 4 FAIL: {e}", flush=True)

try:
    from sgpt.config import cfg
    print("STEP 5: config OK", flush=True)
except Exception as e:
    print(f"STEP 5 FAIL: {e}", flush=True)

try:
    from sgpt.function import get_openai_schemas
    print("STEP 6: function OK", flush=True)
except Exception as e:
    print(f"STEP 6 FAIL: {e}", flush=True)

try:
    from sgpt.role import DefaultRoles, SystemRole
    print("STEP 7: role OK", flush=True)
except Exception as e:
    print(f"STEP 7 FAIL: {e}", flush=True)

try:
    import sgpt
    print("STEP 8: sgpt OK", flush=True)
except Exception as e:
    print(f"STEP 8 FAIL: {e}", flush=True)

print("ALL DONE", flush=True)
