import sys
import os
import subprocess

DEPRECATION_MSG = """
================================================================
WARNING: main.py is DEPRECATED and will be removed in a future release.
This file uses the legacy Orchestrator (pre-V11).

The correct entry point for the V11 Institutional Trading System is:

    python run_247.py

This includes:
  - 7 timeframes (1m, 5m, 15m, 30m, 1h, 2h, 4h)
  - ML prediction gate with adaptive scoring
  - Risk Governor (6 portfolio-level checks)
  - Tail-Risk Sentinel (7 trigger conditions)
  - Regime Classifier (5-regime detection)
  - Diagnostics Engine (PSI drift, attribution)
  - A/B/AZ partition testing
  - Canary deployment framework
  - Web dashboard at http://127.0.0.1:5000
================================================================
"""

print(DEPRECATION_MSG)

if __name__ == '__main__':
    run_247 = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run_247.py')
    if os.path.exists(run_247):
        print("Redirecting to run_247.py...")
        subprocess.run([sys.executable, run_247] + sys.argv[1:])
    else:
        print("ERROR: run_247.py not found. Exiting.")
        sys.exit(1)

