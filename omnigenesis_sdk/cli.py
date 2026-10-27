"""OMNIGENESIS-Ω Command-Line Interface (`omnigenesis`)."""
import argparse
import json
from omnigenesis_sdk.client import OmniGenesisClient

def main() -> None:
    parser = argparse.ArgumentParser(prog='omnigenesis', description='OMNIGENESIS-Ω v6.0 CLI')
    parser.add_argument('command', choices=['pqc', 'science', 'contract'], help='Subsystem command to execute')
    parser.add_argument('--candidate', default='LaH10-Topological-Cage-Dopant-Omega')
    parser.add_argument('--org', default='Aegis Sovereign Defense & Semiconductor Corp.')
    args = parser.parse_args()
    client = OmniGenesisClient()
    if args.command == 'pqc':
        print(json.dumps(client.encapsulate_pqc(), indent=2))
    elif args.command == 'science':
        print(json.dumps(client.discover_material(args.candidate), indent=2))
    elif args.command == 'contract':
        print(json.dumps(client.generate_pilot_contract(args.org), indent=2))

if __name__ == '__main__':
    main()
