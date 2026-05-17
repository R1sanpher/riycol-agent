"""Test sgpt entry point directly with full traceback"""
import sys
import traceback
sys.argv = ['sgpt', '--version']
try:
    from sgpt import cli
    cli()
except Exception:
    traceback.print_exc()
    sys.exit(1)
