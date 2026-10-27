"""Offline administration. Run with the same OMNIGENESIS_DATA_DIR as the server."""
import argparse
import getpass
import json
import sqlite3
from pathlib import Path

from platform_security import IdentityStore, data_directory, migrate_legacy_data, rotate_signing_key, copy_private_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('bootstrap')
    commands.add_parser('migrate-legacy')
    commands.add_parser('rotate-signing-key').add_argument('tag')
    create = commands.add_parser('create-user')
    create.add_argument('username')
    create.add_argument('--role', choices=['admin', 'operator', 'reader'], default='reader')
    for name in ('set-password', 'disable-user'):
        commands.add_parser(name).add_argument('username')
    commands.add_parser('backup').add_argument('destination', type=Path)
    args = parser.parse_args()
    if args.command == 'migrate-legacy':
        print('Migrated:', ', '.join(migrate_legacy_data()) or 'No legacy files to migrate')
        return
    if args.command == 'rotate-signing-key':
        rotate_signing_key(args.tag)
        print('Signing key rotated. Restart all application processes.')
        return
    if args.command == 'backup':
        source = data_directory()
        target = args.destination.expanduser().resolve()
        if target == source.resolve() or source.resolve() in target.parents:
            parser.error('Backup destination must be outside the data directory')
        target.mkdir(mode=0o700, parents=True, exist_ok=False)
        # Each SQLite snapshot is transactional. Stop the app first for a cross-database snapshot.
        for path in source.iterdir():
            if path.suffix == '.sqlite3':
                with sqlite3.connect(path) as original, sqlite3.connect(target / path.name) as backup:
                    original.backup(backup)
                    if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise RuntimeError('Backup integrity check failed')
                (target / path.name).chmod(0o600)
            elif not path.name.endswith(('-wal', '-shm')):
                copy_private_path(path, target / path.name)
        manifest = target / 'backup-manifest.json'
        manifest.write_text(json.dumps({'format': 1, 'sqlite_integrity': 'ok'}))
        manifest.chmod(0o600)
        print(f'Private backup created at {target}. It contains credentials and signing keys.')
        return
    store = IdentityStore()
    try:
        if args.command == 'bootstrap':
            path = store.bootstrap()
            print(f'Initial admin credentials: {path}' if path else 'Accounts already exist; bootstrap skipped.')
        elif args.command in ('create-user', 'set-password'):
            password = getpass.getpass('New password (at least 14 characters): ')
            if password != getpass.getpass('Confirm password: '):
                parser.error('Passwords do not match')
            if args.command == 'create-user':
                store.create_user(args.username, password, args.role)
            else:
                store.set_password(args.username, password)
            print('Account updated.')
        else:
            store.disable_user(args.username)
            print('Account disabled and sessions revoked.')
    finally:
        store.close()


if __name__ == '__main__':
    main()
