"""Local private-beta identities, revocable sessions, and protected data files."""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path


def data_directory():
    path = Path(os.environ.get('OMNIGENESIS_DATA_DIR', str(Path.home() / '.local/share/omnigenesis'))).expanduser()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def data_path(name):
    return data_directory() / name


def connect_database(path, **kwargs):
    options = {"timeout": 30, "check_same_thread": False, **kwargs}
    connection = sqlite3.connect(path, **options)
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA foreign_keys=ON")
    if str(path) != ":memory:":
        Path(path).chmod(0o600)
        connection.execute("PRAGMA journal_mode=WAL")
    return connection


_file_lock = threading.RLock()


def signing_key_bytes(tag):
    """Tags name independent random keys; they never supply key material."""
    directory = data_path('keys')
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / (hashlib.sha256(tag.encode()).hexdigest() + '.key')
    with _file_lock:
        if not path.exists():
            # Atomic publication prevents readers observing a partially written key.
            temporary = directory / ('.key-' + secrets.token_hex(16))
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(secrets.token_bytes(32))
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                pass
            finally:
                temporary.unlink()
        path.chmod(0o600)
        key = path.read_bytes()
        if len(key) != 32:
            raise RuntimeError('Invalid signing key file; restore it from a trusted backup')
        return key


class IdentityStore:
    SESSION_TTL = 3600

    def __init__(self, path=None):
        self.path = str(path or data_path('identities.sqlite3'))
        self.lock = threading.RLock()
        self.connection = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY, salt TEXT NOT NULL, password_hash TEXT NOT NULL,
                role TEXT NOT NULL, disabled INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, expires_at REAL NOT NULL);
        ''')
        if self.path != ':memory:':
            Path(self.path).chmod(0o600)
        self.dummy_salt = secrets.token_bytes(16)

    @staticmethod
    def password_hash(password, salt):
        return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32).hex()

    def create_user(self, username, password, role='reader'):
        if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_.@-]{1,80}', username):
            raise ValueError('Username must use 1–80 letters, digits, or _.@-')
        if not isinstance(password, str) or not 14 <= len(password) <= 1024:
            raise ValueError('Password must contain 14–1024 characters')
        if role not in ('admin', 'operator', 'reader'):
            raise ValueError('Invalid role')
        salt = secrets.token_bytes(16)
        password_hash = self.password_hash(password, salt)
        with self.lock, self.connection:
            self.connection.execute('INSERT INTO users VALUES (?, ?, ?, ?, 0)',
                                    (username, salt.hex(), password_hash, role))

    def bootstrap(self):
        """Provision only an empty installation; never overwrite an account."""
        with self.lock:
            if self.connection.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                return None
            password = secrets.token_urlsafe(24)
            self.create_user('admin', password, 'admin')
            path = data_path('bootstrap-admin.txt')
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as stream:
                stream.write('Username: admin\nPassword: ' + password + '\n')
            return path

    def login(self, username, password):
        if not isinstance(username, str) or not isinstance(password, str) or len(username) > 80 or len(password) > 1024:
            return None
        with self.lock:
            row = self.connection.execute('SELECT salt, password_hash, role, disabled FROM users WHERE username=?',
                                          (username,)).fetchone()
            salt = bytes.fromhex(row[0]) if row else self.dummy_salt
            candidate = self.password_hash(password, salt)
            if not row or not hmac.compare_digest(candidate, row[1]) or row[3]:
                return None
            token = secrets.token_urlsafe(48)
            expires_at = time.time() + self.SESSION_TTL
            with self.connection:
                self.connection.execute('DELETE FROM sessions WHERE expires_at <= ?', (time.time(),))
                self.connection.execute('INSERT INTO sessions VALUES (?, ?, ?)',
                                        (hashlib.sha256(token.encode()).hexdigest(), username, expires_at))
            return {'access_token': token, 'token_type': 'Bearer', 'expires_in': self.SESSION_TTL,
                    'username': username, 'role': row[2]}

    def authenticate(self, token):
        if not token or len(token) > 512:
            return None
        with self.lock:
            row = self.connection.execute('''SELECT u.username, u.role FROM sessions s
                JOIN users u ON s.username=u.username WHERE s.token_hash=? AND s.expires_at>? AND u.disabled=0''',
                (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
        return {'username': row[0], 'role': row[1]} if row else None

    def logout(self, token):
        with self.lock, self.connection:
            self.connection.execute('DELETE FROM sessions WHERE token_hash=?',
                                    (hashlib.sha256(token.encode()).hexdigest(),))

    def set_password(self, username, password):
        if not 14 <= len(password) <= 1024:
            raise ValueError('Password must contain 14–1024 characters')
        salt = secrets.token_bytes(16)
        digest = self.password_hash(password, salt)
        with self.lock, self.connection:
            result = self.connection.execute('UPDATE users SET salt=?,password_hash=? WHERE username=?',
                                             (salt.hex(), digest, username))
            if not result.rowcount:
                raise ValueError('User not found')
            self.connection.execute('DELETE FROM sessions WHERE username=?', (username,))
        bootstrap = data_path('bootstrap-admin.txt')
        if username == 'admin' and bootstrap.exists():
            bootstrap.unlink()

    def disable_user(self, username):
        with self.lock, self.connection:
            self.connection.execute('UPDATE users SET disabled=1 WHERE username=?', (username,))
            self.connection.execute('DELETE FROM sessions WHERE username=?', (username,))

    def close(self):
        self.connection.close()


class RateLimiter:
    """Bounded, per-process fixed windows. Use a gateway limit across workers."""
    def __init__(self):
        self.lock = threading.Lock()
        self.windows = {}

    def allow(self, key, limit=120, seconds=60):
        now = time.monotonic()
        with self.lock:
            if len(self.windows) >= 4096:
                self.windows = {k: v for k, v in self.windows.items() if now - v[0] < seconds}
                if key not in self.windows and len(self.windows) >= 4096:
                    return False
            started, count = self.windows.get(key, (now, 0))
            if now - started >= seconds:
                started, count = now, 0
            self.windows[key] = (started, count + 1)
            return count < limit


def audit_event(**event):
    """Only callers' selected metadata is recorded, never bodies or credentials."""
    with _file_lock:
        path = data_path('audit.jsonl')
        if path.exists() and path.stat().st_size > 5 * 1024 * 1024:
            path.replace(data_path('audit.previous.jsonl'))
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, 'a') as stream:
            stream.write(json.dumps({'timestamp': time.time(), **event}) + '\n')


def copy_private_path(source, destination):
    """Portable content copy for proot: do not copy unsupported extended attributes."""
    import shutil
    source, destination = Path(source), Path(destination)
    if source.is_symlink():
        raise ValueError("Refusing to include a symbolic link in a private data copy")
    if source.is_dir():
        destination.mkdir(mode=0o700)
        for child in source.iterdir():
            copy_private_path(child, destination / child.name)
    else:
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with source.open('rb') as original, os.fdopen(fd, 'wb') as target:
            shutil.copyfileobj(original, target)


def migrate_legacy_data(legacy_directory=Path('/tmp')):
    """Copy legacy stores without replacing durable files. SQLite uses its backup API."""
    import shutil
    migrated = []
    names = (
        'omnigenesis_production.sqlite3', 'omnigenesis_agent_economy.sqlite3',
        'omnigenesis_sovereign_cloud.sqlite3', 'omnigenesis_computer_use.sqlite3',
        'omnigenesis_vector_rag.sqlite3', 'omnigenesis_timetravel_debugger.sqlite3',
        'omnigenesis_biofoundry.sqlite3', 'omnigenesis_governance_dao.sqlite3',
        'omnigenesis_episodic_vault.json',
    )
    for name in names:
        source, destination = Path(legacy_directory) / name, data_path(name)
        if not source.is_file() or destination.exists():
            continue
        temporary = destination.with_name('.migration-' + secrets.token_hex(16))
        try:
            if name.endswith('.sqlite3'):
                with sqlite3.connect(source) as original, sqlite3.connect(temporary) as target:
                    original.backup(target)
                    if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise RuntimeError('Legacy database integrity check failed')
            else:
                copy_private_path(source, temporary)
            temporary.chmod(0o600)
            try:
                os.link(temporary, destination)
                migrated.append(name)
            except FileExistsError:
                pass
        finally:
            if temporary.exists():
                temporary.unlink()
    deployments = Path(legacy_directory) / 'omnicloud_deployments'
    if deployments.is_dir() and not data_path('deployments').exists():
        copy_private_path(deployments, data_path('deployments'))
        migrated.append('deployments')
    return migrated


def rotate_signing_key(tag):
    """Archive only the previous public key. Restart processes after rotation."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    with _file_lock:
        old = signing_key_bytes(tag)
        key_id = hashlib.sha256(tag.encode()).hexdigest()
        directory = data_path('keys')
        public = Ed25519PrivateKey.from_private_bytes(old).public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        (directory / (key_id + '-' + secrets.token_hex(8) + '.public')).write_bytes(public)
        temporary = directory / ('.rotate-' + secrets.token_hex(16))
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(secrets.token_bytes(32))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(directory / (key_id + '.key'))
