"""HTTP regression checks against an ephemeral authenticated platform server."""
import json
import threading
import os
import tempfile
import socket
from unittest.mock import patch
import unittest
import urllib.error
import urllib.request

from omnigenesis_engine import create_production_http_server


class PlatformHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {"OMNIGENESIS_DATA_DIR": temporary.name, "OMNIGENESIS_PRIVATE_BETA": "0"})
        environment.start()
        cls.addClassCleanup(environment.stop)
        cls.keys = {role: f'regression-{role}-key-' + 'a' * 40
                    for role in ('admin', 'operator', 'reader')}
        cls.server, port = create_production_http_server(
            port=0, api_credentials=cls.keys, jwt_signing_secret='regression-jwt-' + 'b' * 40)
        cls.base = f'http://127.0.0.1:{port}'
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def request(self, path, *, method='GET', role='admin', body=None, raw=None, headers=None):
        request_headers = dict(headers or {})
        if role:
            request_headers['Authorization'] = f'Bearer {self.keys[role]}'
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            request_headers.setdefault('Content-Type', 'application/json')
        req = urllib.request.Request(self.base + path, data=data,
                                     headers=request_headers, method=method)
        try:
            return urllib.request.urlopen(req, timeout=15)
        except urllib.error.HTTPError as error:
            return error

    def test_public_health_and_dashboard(self):
        with self.request('/api/health', role=None) as response:
            self.assertEqual(json.load(response), {'status': 'ok'})
        with self.request('/', role=None) as response:
            self.assertIn(b'platform-connection-status', response.read())

    def test_readiness_fails_when_storage_is_unavailable(self):
        with patch.object(self.server, 'check_readiness', side_effect=OSError('disk unavailable')):
            with self.request('/api/health', role=None) as response:
                self.assertEqual(response.status, 503)
                self.assertEqual(json.load(response), {'status': 'unavailable'})
        with self.request('/api/health', role=None) as response:
            self.assertEqual(response.status, 200)

    def test_health_probe_is_not_blocked_by_request_throttle(self):
        with patch('platform_security.RateLimiter.allow', return_value=False):
            with self.request('/api/health', role=None) as response:
                self.assertEqual(response.status, 200)
            with self.request('/api/routes') as response:
                self.assertEqual(response.status, 429)

    def test_ambiguous_http_framing_is_rejected(self):
        for framing in (b'Content-Length: 2\r\nContent-Length: 2\r\n',
                        b'Content-Length: 2\r\nTransfer-Encoding: chunked\r\n',
                        b'Content-Length: +2\r\n',
                        b'Transfer-Encoding: chunked\r\n'):
            with self.subTest(framing=framing):
                with socket.create_connection(self.server.server_address, timeout=5) as connection:
                    connection.sendall(b'POST /api/auth/login HTTP/1.1\r\nHost: localhost\r\n'
                                       b'Content-Type: application/json\r\n' + framing + b'\r\n{}')
                    self.assertIn(b' 400 ', connection.recv(4096).split(b'\r\n')[0])

    def test_state_requires_authentication(self):
        with self.request('/api/state', role=None) as response:
            self.assertEqual(response.status, 401)

    def test_reader_cannot_mutate(self):
        with self.request('/api/reset', method='POST', role='reader', body={}) as response:
            self.assertEqual(response.status, 403)

    def test_operator_cannot_access_admin_state(self):
        with self.request('/api/state', role='operator') as response:
            self.assertEqual(response.status, 403)

    def test_guide_is_registered(self):
        with self.request('/v1/guide', role='reader') as response:
            self.assertEqual(response.status, 200)
            self.assertTrue(json.load(response)['steps'])

    def test_unknown_route_returns_404(self):
        with self.request('/v1/missing') as response:
            self.assertEqual(response.status, 404)

    def test_malformed_json_is_rejected(self):
        with self.request('/api/converge', method='POST', raw=b'{bad',
                          headers={'Content-Type': 'application/json'}) as response:
            self.assertEqual(response.status, 400)

    def test_array_json_is_rejected(self):
        with self.request('/api/converge', method='POST', body=[]) as response:
            self.assertEqual(response.status, 400)

    def test_wrong_content_type_is_rejected(self):
        with self.request('/api/converge', method='POST', raw=b'{}') as response:
            self.assertEqual(response.status, 415)

    def test_invalid_numeric_input_returns_json(self):
        with self.request('/v1/operators/execute', method='POST', body={'x1': 'invalid'}) as response:
            self.assertEqual(response.status, 400)
            self.assertIn('error', json.load(response))
        with self.request('/api/health') as response:
            self.assertEqual(response.status, 200)

    def test_generic_model_inference_route(self):
        with self.request('/v1/models/infer', method='POST',
                          body={'input_vector': [0.8, 0.9]}) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.load(response)['status'], 'VERIFIED_INFERENCE')

    def test_unknown_model_returns_404(self):
        with self.request('/v1/models/nonexistent-model/infer', method='POST', body={}) as response:
            self.assertEqual(response.status, 404)

    def test_nonfinite_model_input_returns_400(self):
        with self.request('/v1/models/infer', method='POST', body={'input_vector': [float('nan')]}) as response:
            self.assertEqual(response.status, 400)

    def test_convergence_updates_server_state(self):
        with self.request('/api/state') as response:
            before = json.load(response)['cycle']
        with self.request('/api/converge', method='POST', body={'goal': 'Regression goal'}) as response:
            state = json.load(response)['state']
            self.assertEqual(state['cycle'], before + 1)
            self.assertEqual(state['mission_goal'], 'Regression goal')

    def test_metrics_are_real_text(self):
        with self.request('/metrics') as response:
            self.assertIn('text/plain', response.headers['Content-Type'])
            self.assertIn(b'omnigenesis_omega_quotient', response.read())

    def test_sse_delivers_multiple_events(self):
        with self.request('/v1/stream/events') as response:
            self.assertIn('text/event-stream', response.headers['Content-Type'])
            self.assertIsNone(response.headers.get('Content-Length'))
            events = 0
            while events < 2:
                line = response.readline()
                self.assertTrue(line)
                if line.startswith(b'event: omega_telemetry'):
                    events += 1

    def test_untrusted_origin_is_rejected(self):
        with self.request('/api/state', method='OPTIONS', role=None,
                          headers={'Origin': 'https://untrusted.example'}) as response:
            self.assertEqual(response.status, 403)

    def test_unconfigured_identity_provider_stays_disabled(self):
        with self.request('/v1/auth/token', method='POST', body={}) as response:
            self.assertEqual(response.status, 503)

    def test_cloud_path_traversal_is_rejected(self):
        with self.request('/cloud/apps/../../etc/passwd') as response:
            self.assertEqual(response.status, 400)


if __name__ == '__main__':
    unittest.main()
