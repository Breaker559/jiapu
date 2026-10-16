"""Docker acceptance test in a generated project, with disposable data and no extra Python packages."""
import argparse
import http.cookiejar
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import struct
import subprocess
import tempfile
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=['sqlite', 'postgres'], default='sqlite')
    args = parser.parse_args()
    docker = shutil.which('docker')
    if not docker:
        parser.exit(2, 'Docker CLI was not found. Install Docker with a running Linux engine to run this test.\n')
    result = subprocess.run([docker, 'info', '--format', '{{.OSType}}'], capture_output=True, text=True)
    if result.returncode or result.stdout.strip() != 'linux':
        parser.exit(2, 'A running Docker Linux engine is required.\n')
    subprocess.run([docker, 'compose', 'version'], check=True)
    project = 'jiapu-qa-' + secrets.token_hex(6)
    with socket.socket() as candidate:
        candidate.bind(('127.0.0.1', 0))
        port = candidate.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    env = {key: value for key, value in os.environ.items() if not key.startswith('COMPOSE_')}
    env.update(QINPU_BIND_ADDRESS='127.0.0.1', QINPU_PORT=str(port),
               QINPU_ALLOWED_HOSTS='family.example.test', QINPU_ORIGINS=base,
               QINPU_SECURE_COOKIE='0', QINPU_TRUSTED_PROXIES='127.0.0.1',
               QINPU_DB_PASSWORD=secrets.token_hex(32))
    with tempfile.TemporaryDirectory(prefix=project + '-') as scratch:
        envfile = Path(scratch) / '.env'
        envfile.write_text('', encoding='utf-8')
        compose = [docker, 'compose', '--env-file', str(envfile), '-p', project,
                   '-f', str(ROOT / ('compose.sqlite.yaml' if args.backend == 'sqlite' else 'compose.yaml'))]

        def run(*arguments, capture=False, check=True, timeout=120):
            return subprocess.run([*compose, *arguments], cwd=ROOT, env=env, check=check,
                                  capture_output=capture, text=True, timeout=timeout)

        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        csrf = ''

        def request(path, data=None, content_type=None):
            headers = {'Origin': base}
            if csrf:
                headers['X-CSRF-Token'] = csrf
            if data is not None:
                if content_type:
                    headers['Content-Type'] = content_type
                else:
                    headers['Content-Type'] = 'application/json'
                    data = json.dumps(data).encode()
            with opener.open(urllib.request.Request(base + path, data=data, headers=headers), timeout=30) as response:
                return response.read()

        def api(path, data=None):
            return json.loads(request(path, data))

        run('config', '--quiet')
        print(f'Testing {args.backend} in disposable project {project} on port {port}', flush=True)
        try:
            run('up', '-d', '--build', '--wait', '--wait-timeout', '120', timeout=1200)
            assert api('/api/health')['ok']
            markup = request('/').decode()
            assert '<title>家谱' in markup and '亲谱' not in markup
            for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', markup):
                assert request(asset), asset
            assert run('exec', '-T', 'app', 'python', '-c', 'import os; print(os.getuid())', capture=True).stdout.strip() == '10001'
            auth = api('/api/setup', {'name': '容器验收', 'email': 'docker@example.test', 'password': secrets.token_hex(16), 'demo': False})
            csrf = auth['csrf']
            fid = auth['families'][0]['id']
            person = api(f'/api/families/{fid}/records/person', {'data': {'name': '重建后仍存在的人物', 'gender': 'female'}})

            # Produce a valid PNG with only the standard library.
            def chunk(kind, body):
                return struct.pack('!I', len(body)) + kind + body + struct.pack('!I', zlib.crc32(kind + body))
            photo = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 2, 2, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress((b'\0' + b'\x80\xa0\x90' * 2) * 2)) + chunk(b'IEND', b'')
            boundary = 'jiapu-' + secrets.token_hex(12)
            metadata = json.dumps({'title': '容器照片', 'person_ids': [person['id']]})
            multipart = (f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n{metadata}\r\n'
                         f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="photo.png"\r\nContent-Type: image/png\r\n\r\n').encode() + photo + f'\r\n--{boundary}--\r\n'.encode()
            media = json.loads(request(f'/api/families/{fid}/media', multipart, 'multipart/form-data; boundary=' + boundary))
            assert request(f'/api/families/{fid}/media/{media["id"]}/original') == photo
            if args.backend == 'sqlite':
                run('exec', '-T', 'app', 'python', '-c', 'from pathlib import Path; assert Path("/app/data/qinpu.db").is_file()')

            # Recreate containers without deleting named volumes. Existing login sessions must survive too.
            run('up', '-d', '--no-build', '--force-recreate', '--wait', '--wait-timeout', '120', timeout=240)
            rows = api(f'/api/families/{fid}/state')['records']
            assert any(row['id'] == person['id'] and row['data']['name'] == '重建后仍存在的人物' for row in rows)
            assert request(f'/api/families/{fid}/media/{media["id"]}/original') == photo
            assert api('/api/me')['user']['email'] == 'docker@example.test'
            print(json.dumps({'passed': True, 'backend': args.backend, 'checks': ['image-build', 'health-with-custom-domain', 'frontend-assets', 'non-root', 'setup', 'person', 'photo', 'recreated-container-persistence', 'persistent-login']}, ensure_ascii=False))
        except Exception:
            run('logs', '--no-color', '--tail=80', check=False)
            raise
        finally:
            # Only this locally generated test namespace can be removed, never a configured deployment.
            assert re.fullmatch(r'jiapu-qa-[0-9a-f]{12}', project)
            run('down', '--volumes', '--remove-orphans', check=True)


if __name__ == '__main__':
    main()
