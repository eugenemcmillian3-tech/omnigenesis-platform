"""OMNIGENESIS-Ω Official Python SDK Client (Direct Engine + HTTP REST Bridge)."""
import json
import urllib.request
from typing import Any, Dict, Optional

class OmniGenesisClient:
    def __init__(self, base_url: Optional[str] = None, api_key: str = 'sk-omni-live-enterprise') -> None:
        self.base_url = base_url.rstrip('/') if base_url else None
        self.api_key = api_key
        self._local_engine = None

    def _get_local(self):
        if self._local_engine is None:
            try:
                import omnigenesis_engine as _eng
            except ImportError:
                from omnigenesis_sdk import engine as _eng
            self._local_engine = _eng
        return self._local_engine

    def encapsulate_pqc(self, seed_phrase: str = 'OMNIGENESIS_PQC_QUANTUM_SAFE_SEED') -> Dict[str, Any]:
        if self.base_url:
            req = urllib.request.Request(
                f'{self.base_url}/v1/pqc/encapsulate',
                data=json.dumps({'seed_phrase': seed_phrase}).encode('utf-8'),
                headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode('utf-8'))
        return self._get_local().PostQuantumLatticeCryptoEngine.encapsulate_and_verify_pqc(seed_phrase)

    def discover_material(self, candidate: str = 'LaH10-Topological-Cage-Dopant-Omega', lambda_ep: float = 2.48, omega_log_kelvin: float = 1420.0, mu_star: float = 0.11) -> Dict[str, Any]:
        if self.base_url:
            req = urllib.request.Request(
                f'{self.base_url}/v1/science/discover',
                data=json.dumps({'material_candidate': candidate, 'lambda_ep': lambda_ep, 'omega_log_kelvin': omega_log_kelvin, 'mu_star': mu_star}).encode('utf-8'),
                headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode('utf-8'))
        return self._get_local().AutonomousScientificDiscoveryEngine.run_materials_and_molecular_discovery(candidate, lambda_ep, omega_log_kelvin, mu_star)

    def generate_pilot_contract(self, customer_org: str = 'Aegis Sovereign Defense & Semiconductor Corp.', annual_acv_usd: int = 850000) -> Dict[str, Any]:
        return self._get_local().NinetyDayGTMPlaybookAndContractEngine.generate_pilot_contract(customer_org=customer_org, annual_acv_usd=annual_acv_usd)
