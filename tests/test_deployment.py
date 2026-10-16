"""Exercise production host/cookie settings in a fresh process and disposable database."""
import os
from pathlib import Path
import subprocess
import sys


def test_public_domain_keeps_health_probe_and_secure_login_working(tmp_path):
    env = {**os.environ, 'QINPU_DATA': str(tmp_path),
           'QINPU_ALLOWED_HOSTS': ' family.example.test , other.example.test ',
           'QINPU_ORIGINS': ' https://other.example.test/ ', 'QINPU_SECURE_COOKIE': '1'}
    env.pop('DATABASE_URL', None)
    code = '''
from fastapi.testclient import TestClient
from server.app import app
with TestClient(app, base_url='https://family.example.test') as client:
    assert client.get('/api/health').status_code == 200
    assert client.get('/api/health', headers={'Host': '127.0.0.1:8765'}).status_code == 200
    assert client.get('/api/health', headers={'Host': 'localhost:8765'}).status_code == 200
    assert client.get('/api/health', headers={'Host': 'untrusted.example.test'}).status_code == 400
    created = client.post('/api/setup', json={'name': 'Deployment test', 'email': 'deployment@example.test', 'password': 'deployment-password', 'demo': False}, headers={'Origin': 'https://other.example.test'})
    assert created.status_code == 200, created.text
    assert 'Secure' in created.headers['set-cookie']
    assert client.get('/api/me').status_code == 200
    assert client.get('/api/me').headers['strict-transport-security'] == 'max-age=31536000'
    forbidden = client.post('/api/families', json={'name': 'Rejected'}, headers={'Origin': 'https://untrusted.example.test', 'X-CSRF-Token': created.json()['csrf']})
    assert forbidden.status_code == 403
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).resolve().parent.parent,
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
