"""Run regressions and the built-in suite against separate disposable data directories."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='omni-regressions-') as directory:
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                   cwd=root, env={**os.environ, 'OMNIGENESIS_DATA_DIR': directory,
                                  'OMNIGENESIS_PRIVATE_BETA': '0'}, check=True)
with tempfile.TemporaryDirectory(prefix='omni-self-test-') as directory:
    result = subprocess.run([sys.executable, 'omnigenesis_engine.py', '--self-test'],
                            cwd=root, env={**os.environ, 'OMNIGENESIS_DATA_DIR': directory,
                                           'OMNIGENESIS_PRIVATE_BETA': '1'},
                            capture_output=True, text=True, check=True, timeout=120)
    report = json.loads(result.stdout)
    if not report.get('all_passed'):
        raise SystemExit('Built-in verification failed')
    print(f"Built-in verification: {report['total_checks']} checks passed")
