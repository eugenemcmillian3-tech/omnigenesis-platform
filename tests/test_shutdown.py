"""Exercise real deployment termination and checkpoint persistence."""
import json
import os
from pathlib import Path
import selectors
import signal
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import urllib.request


class DeploymentShutdownTests(unittest.TestCase):
    def test_sigterm_exits_cleanly_and_saves_checkpoint(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            environment = {**os.environ, 'OMNIGENESIS_DATA_DIR': directory,
                           'OMNIGENESIS_PRIVATE_BETA': '1',
                           'OMNIGENESIS_BIND_HOST': '127.0.0.1',
                           'OMNIGENESIS_JWT_SECRET': 'shutdown-jwt-' + 'y' * 40,
                           'OMNIGENESIS_ADMIN_API_KEY': 'shutdown-test-' + 'x' * 40}
            process = subprocess.Popen(
                [sys.executable, '-u', 'omnigenesis_engine.py', '--serve', '--port', '0'],
                cwd=root, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    self.assertTrue(selector.select(timeout=30), 'Server did not start')
                    line = process.stdout.readline()
                    if b'API listening' not in line:
                        output, _ = process.communicate(timeout=10)
                        self.fail((line + output).decode())
                port = int(line.decode().strip().rsplit(':', 1)[1])
                request = urllib.request.Request(
                    f'http://127.0.0.1:{port}/v1/stream/events',
                    headers={'Authorization': 'Bearer ' + environment['OMNIGENESIS_ADMIN_API_KEY']})
                with urllib.request.urlopen(request, timeout=5) as stream:
                    self.assertIn(b'omega_telemetry', stream.readline())
                    process.send_signal(signal.SIGTERM)
                    output, _ = process.communicate(timeout=20)
                    # A live SSE connection must end instead of holding up deploy shutdown.
                    stream.read()
                self.assertEqual(process.returncode, 0, output.decode())
                self.assertIn(b'shutdown complete', output)
                with sqlite3.connect(Path(directory) / 'omnigenesis_production.sqlite3') as connection:
                    self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                    checkpoint = connection.execute('SELECT payload FROM runtime_checkpoint').fetchone()
                    self.assertIsNotNone(checkpoint)
                    self.assertTrue(json.loads(checkpoint[0]))
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()


if __name__ == '__main__':
    unittest.main()
