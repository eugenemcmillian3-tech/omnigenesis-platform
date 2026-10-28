import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from omnigenesis_engine import OmniGenesisProductionDB, OmniGenesisSingularityCore, create_production_http_server
from platform_security import IdentityStore, RateLimiter, data_path, migrate_legacy_data, rotate_signing_key, signing_key_bytes


class SecurityStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict(os.environ, {'OMNIGENESIS_DATA_DIR': self.directory.name})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.store = IdentityStore()
        self.addCleanup(self.store.close)

    def test_password_hash_and_session_revocation(self):
        password = 'correct horse battery private beta'
        self.store.create_user('alice', password, 'admin')
        raw = self.store.connection.execute('SELECT password_hash FROM users').fetchone()[0]
        self.assertNotEqual(raw, password)
        self.assertIsNone(self.store.login('alice', 'incorrect password'))
        token = self.store.login('alice', password)['access_token']
        self.assertEqual(self.store.authenticate(token)['username'], 'alice')
        self.store.logout(token)
        self.assertIsNone(self.store.authenticate(token))

    def test_owner_setup_requires_key_and_is_one_time(self):
        key = 'owner-setup-' + 'z' * 40
        self.assertTrue(self.store.setup_available(key))
        self.assertIsNone(self.store.setup_owner('owner@example.com', 'a long owner password', 'wrong', key))
        self.assertIsNone(self.store.setup_owner('owner@example.com', 'a long owner password', '', ''))
        result = self.store.setup_owner('Owner@Example.com', 'a long owner password', key, key)
        self.assertEqual(result['username'], 'owner@example.com')
        self.assertEqual(len(result['recovery_codes']), 8)
        self.assertEqual(self.store.login('owner@example.com', 'a long owner password')['role'], 'admin')
        self.assertFalse(self.store.setup_available(key))
        self.assertIsNone(self.store.setup_owner('attacker@example.com', 'a long owner password', key, key))
        reopened = IdentityStore()
        try:
            self.assertFalse(reopened.setup_available(key))
        finally:
            reopened.close()

    def test_recovery_revokes_sessions_and_all_previous_codes(self):
        key = 'owner-setup-' + 'z' * 40
        setup = self.store.setup_owner('owner@example.com', 'a long owner password', key, key)
        token = self.store.login('owner@example.com', 'a long owner password')['access_token']
        first, second = setup['recovery_codes'][:2]
        stored = [row[0] for row in self.store.connection.execute('SELECT code_hash FROM recovery_codes')]
        self.assertNotIn(first, stored)
        self.assertIsNone(self.store.recover_password('missing@example.com', first, 'a changed owner password'))
        self.assertIsNone(self.store.recover_password('owner@example.com', 'wrong', 'a changed owner password'))
        result = self.store.recover_password('OWNER@example.com', first, 'a changed owner password')
        self.assertEqual(len(result['recovery_codes']), 8)
        self.assertIsNone(self.store.authenticate(token))
        self.assertIsNone(self.store.login('owner@example.com', 'a long owner password'))
        self.assertIsNotNone(self.store.login('owner@example.com', 'a changed owner password'))
        for code in [first, second]:
            self.assertIsNone(self.store.recover_password('owner@example.com', code, 'another owner password'))

    def test_disabled_account_cannot_recover(self):
        key = 'owner-setup-' + 'z' * 40
        setup = self.store.setup_owner('owner@example.com', 'a long owner password', key, key)
        self.store.disable_user('owner@example.com')
        self.assertIsNone(self.store.recover_password('owner@example.com', setup['recovery_codes'][0], 'a changed owner password'))

    def test_password_change_requires_current_password(self):
        self.store.create_user('alice', 'original user password')
        token = self.store.login('alice', 'original user password')['access_token']
        self.assertIsNone(self.store.change_password('alice', 'wrong', 'replacement user password'))
        self.assertIsNotNone(self.store.authenticate(token))
        result = self.store.change_password('alice', 'original user password', 'replacement user password')
        self.assertEqual(len(result['recovery_codes']), 8)
        self.assertIsNone(self.store.authenticate(token))
        self.assertEqual(self.store.login('alice', 'replacement user password')['role'], 'reader')

    def test_expired_sessions_are_rejected(self):
        self.store.create_user('alice', 'a long enough password')
        token = self.store.login('alice', 'a long enough password')['access_token']
        with self.store.connection:
            self.store.connection.execute('UPDATE sessions SET expires_at=?', (time.time() - 1,))
        self.assertIsNone(self.store.authenticate(token))

    def test_password_change_and_disable_revoke_sessions(self):
        self.store.create_user('alice', 'a long enough password')
        old = self.store.login('alice', 'a long enough password')['access_token']
        self.store.set_password('alice', 'a different long password')
        self.assertIsNone(self.store.authenticate(old))
        new = self.store.login('alice', 'a different long password')['access_token']
        self.store.disable_user('alice')
        self.assertIsNone(self.store.authenticate(new))
        self.assertIsNone(self.store.login('alice', 'a different long password'))

    def test_accounts_and_sessions_survive_reopen(self):
        self.store.create_user('alice', 'a long enough password')
        token = self.store.login('alice', 'a long enough password')['access_token']
        reopened = IdentityStore()
        try:
            self.assertEqual(reopened.authenticate(token)['role'], 'reader')
        finally:
            reopened.close()

    def test_bootstrap_never_overwrites_existing_account(self):
        credential_file = self.store.bootstrap()
        self.assertIsNotNone(credential_file)
        self.assertEqual(credential_file.stat().st_mode & 0o777, 0o600)
        original = credential_file.read_bytes()
        self.assertIsNone(self.store.bootstrap())
        self.assertEqual(credential_file.read_bytes(), original)
        self.store.set_password('admin', 'a new private admin password')
        self.assertFalse(credential_file.exists())

    def test_signing_keys_are_random_persistent_and_rotatable(self):
        key = signing_key_bytes('receipt-test')
        self.assertEqual(signing_key_bytes('receipt-test'), key)
        self.assertNotEqual(key, hashlib.sha256(b'receipt-test').digest())
        self.assertNotEqual(key, signing_key_bytes('other-tag'))
        path = data_path('keys') / (hashlib.sha256(b'receipt-test').hexdigest() + '.key')
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        rotate_signing_key('receipt-test')
        self.assertNotEqual(key, signing_key_bytes('receipt-test'))
        self.assertEqual(len(list(data_path('keys').glob('*.public'))), 1)

    def test_rate_limit_window_resets(self):
        limiter = RateLimiter()
        with patch('platform_security.time.monotonic', return_value=1):
            self.assertTrue(limiter.allow('client', limit=1))
            self.assertFalse(limiter.allow('client', limit=1))
        with patch('platform_security.time.monotonic', return_value=62):
            self.assertTrue(limiter.allow('client', limit=1))

    def test_legacy_migration_preserves_source_and_existing_target(self):
        with tempfile.TemporaryDirectory() as legacy:
            source = Path(legacy) / 'omnigenesis_production.sqlite3'
            with sqlite3.connect(source) as connection:
                connection.execute('CREATE TABLE marker (value TEXT)')
                connection.execute("INSERT INTO marker VALUES ('original')")
            self.assertIn(source.name, migrate_legacy_data(Path(legacy)))
            with sqlite3.connect(data_path(source.name)) as connection:
                self.assertEqual(connection.execute('SELECT value FROM marker').fetchone()[0], 'original')
                connection.execute("UPDATE marker SET value='changed'")
            migrate_legacy_data(Path(legacy))
            with sqlite3.connect(data_path(source.name)) as connection:
                self.assertEqual(connection.execute('SELECT value FROM marker').fetchone()[0], 'changed')
            with sqlite3.connect(source) as connection:
                self.assertEqual(connection.execute('SELECT value FROM marker').fetchone()[0], 'original')

    def test_backup_restores_account_and_key_after_session_revocation(self):
        password = 'a recoverable private password'
        self.store.create_user('backup-user', password)
        token = self.store.login('backup-user', password)['access_token']
        original_key = signing_key_bytes('backup-test')
        with tempfile.TemporaryDirectory() as parent:
            target = Path(parent) / 'backup'
            result = subprocess.run([sys.executable, 'platform_admin.py', 'backup', str(target)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            restored = IdentityStore(target / 'identities.sqlite3')
            try:
                self.assertEqual(restored.connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                # Follow the runbook: restored sessions must be invalidated before restart.
                with restored.connection:
                    restored.connection.execute('DELETE FROM sessions')
                self.assertIsNone(restored.authenticate(token))
                self.assertIsNotNone(restored.login('backup-user', password))
            finally:
                restored.close()
            self.assertEqual(next((target / 'keys').glob('*.key')).read_bytes(), original_key)
            self.assertEqual(target.stat().st_mode & 0o777, 0o700)

    def test_core_checkpoint_restores_goal_cycles_and_operators(self):
        core = OmniGenesisSingularityCore(goal='Durable beta goal')
        core.execute_full_convergence(cycles=2)
        db = OmniGenesisProductionDB()
        self.addCleanup(db.conn.close)
        db.sync_core(core)
        restored = OmniGenesisSingularityCore(goal='Fresh process')
        self.assertTrue(db.restore_core(restored))
        self.assertEqual(restored.goal, core.goal)
        self.assertEqual(restored.telemetry_history, core.telemetry_history)
        self.assertEqual(set(restored.manifest_engine.registry), set(core.manifest_engine.registry))


class BrowserOwnerSetupTests(unittest.TestCase):
    def test_http_setup_requires_owner_proof_and_cannot_be_repeated(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'OMNIGENESIS_DATA_DIR': directory, 'OMNIGENESIS_PRIVATE_BETA': '1',
                'OMNIGENESIS_ACCOUNT_SETUP_KEY': 'setup-test-' + 'z' * 40}):
            server, port = create_production_http_server(
                port=0, api_credentials={'admin': 'setup-service-' + 'a' * 40},
                jwt_signing_secret='setup-jwt-' + 'b' * 40)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            def request(path, body=None):
                req = urllib.request.Request(f'http://127.0.0.1:{port}' + path,
                    data=json.dumps(body).encode() if body is not None else None,
                    headers={'Content-Type': 'application/json'})
                try:
                    response = urllib.request.urlopen(req, timeout=10)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    return response.status, json.load(response)
            try:
                self.assertTrue(request('/api/auth/config')[1]['setup_available'])
                payload = {'email': 'owner@example.com', 'password': 'a browser owner password',
                           'setup_key': 'incorrect'}
                self.assertEqual(request('/api/auth/setup', payload)[0], 400)
                payload['setup_key'] = os.environ['OMNIGENESIS_ACCOUNT_SETUP_KEY']
                status, result = request('/api/auth/setup', payload)
                self.assertEqual(status, 200)
                self.assertEqual(len(result['recovery_codes']), 8)
                self.assertFalse(request('/api/auth/config')[1]['setup_available'])
                self.assertEqual(request('/api/auth/setup', payload)[0], 400)
                status, login = request('/api/auth/login', {'username': 'owner@example.com', 'password': payload['password']})
                self.assertEqual(status, 200)
                self.assertEqual(login['role'], 'admin')
                audit = data_path('audit.jsonl').read_text()
                for secret in [payload['password'], payload['setup_key'], *result['recovery_codes'], login['access_token']]:
                    self.assertNotIn(secret, audit)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)


class BetaLoginHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(directory.cleanup)
        environment = patch.dict(os.environ, {'OMNIGENESIS_DATA_DIR': directory.name, 'OMNIGENESIS_PRIVATE_BETA': '1'})
        environment.start()
        cls.addClassCleanup(environment.stop)
        cls.store = IdentityStore()
        cls.addClassCleanup(cls.store.close)
        cls.store.create_user('beta-admin', 'private beta admin password', 'admin')
        cls.store.create_user('beta-reader', 'private beta reader password', 'reader')
        cls.server, port = create_production_http_server(
            port=0, api_credentials={'admin': 'test-service-key-' + 'a' * 40},
            jwt_signing_secret='test-jwt-secret-' + 'b' * 40, identity_store=cls.store)
        cls.base = f'http://127.0.0.1:{port}'
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.server.server_close)
        cls.addClassCleanup(cls.server.shutdown)

    def request(self, path, body=None, token=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request(self.base + path,
            data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def login(self, username='beta-admin', password='private beta admin password'):
        status, result = self.request('/api/auth/login', {'username': username, 'password': password})
        self.assertEqual(status, 200)
        return result['access_token']

    def test_login_logout_and_identity(self):
        token = self.login()
        status, identity = self.request('/api/auth/me', token=token)
        self.assertEqual(status, 200)
        self.assertEqual(identity['username'], 'beta-admin')
        self.assertEqual(self.request('/api/state', token=token)[0], 200)
        self.assertEqual(self.request('/api/auth/logout', {}, token)[0], 200)
        self.assertEqual(self.request('/api/state', token=token)[0], 401)

    def test_reader_session_cannot_access_admin_state(self):
        token = self.login('beta-reader', 'private beta reader password')
        self.assertEqual(self.request('/v1/guide', token=token)[0], 200)
        self.assertEqual(self.request('/api/state', token=token)[0], 403)

    def test_multi_tenant_provisioning_is_blocked(self):
        self.assertEqual(self.request('/v1/saas/tenants/provision', {}, self.login())[0], 503)

    def test_browser_password_change_and_recovery(self):
        self.store.create_user('browser-reader', 'original browser password', 'reader')
        token = self.login('browser-reader', 'original browser password')
        status, changed = self.request('/api/auth/change-password', {
            'current_password': 'original browser password', 'password': 'changed browser password'}, token)
        self.assertEqual(status, 200)
        self.assertEqual(self.request('/api/auth/me', token=token)[0], 401)
        status, recovered = self.request('/api/auth/recover', {
            'username': 'browser-reader', 'recovery_code': changed['recovery_codes'][0],
            'password': 'recovered browser password'})
        self.assertEqual(status, 200)
        self.assertEqual(len(recovered['recovery_codes']), 8)
        self.assertEqual(self.request('/api/state', token=self.login('browser-reader', 'recovered browser password'))[0], 403)

    def test_setup_is_disabled_without_owner_key(self):
        status, config = self.request('/api/auth/config')
        self.assertEqual(status, 200)
        self.assertFalse(config['setup_available'])
        self.assertEqual(self.request('/api/auth/setup', {
            'email': 'visitor@example.com', 'password': 'a visitor password', 'setup_key': 'anything'})[0], 400)

    def test_api_key_cannot_change_an_account_password(self):
        status, _ = self.request('/api/auth/change-password', {
            'current_password': 'anything', 'password': 'a replacement password'}, 'test-service-key-' + 'a' * 40)
        self.assertEqual(status, 403)

    def test_audit_log_excludes_credentials(self):
        token = self.login()
        self.request('/api/auth/me', token=token)
        log = data_path('audit.jsonl').read_text()
        self.assertIn('beta-admin', log)
        self.assertNotIn(token, log)
        self.assertNotIn('private beta admin password', log)

    def test_zz_login_throttling(self):
        statuses = [self.request('/api/auth/login', {'username': 'unknown', 'password': 'bad'})[0]
                    for _ in range(11)]
        self.assertEqual(statuses[-1], 429)
