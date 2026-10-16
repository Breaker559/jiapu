"""Exercise full-graph export, embedded avatars, privacy and offline browsing."""
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image
from playwright.sync_api import expect, sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'test-results' / ('export-' + str(time.time_ns()))
DATA.mkdir(parents=True)
BASE = 'http://127.0.0.1:8886'
env = {**os.environ, 'QINPU_DATA': str(DATA), 'PYTHONUTF8': '1'}
env.pop('DATABASE_URL', None)
log = (DATA / 'server.log').open('w', encoding='utf-8')
server = subprocess.Popen([str(ROOT / '.venv/Scripts/python.exe'), '-m', 'uvicorn', 'server.app:app', '--host', '127.0.0.1', '--port', '8886'], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
try:
    for _ in range(50):
        try:
            urllib.request.urlopen(BASE + '/api/health', timeout=1)
            break
        except Exception:
            time.sleep(.2)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        ctx = browser.new_context(viewport={'width': 1440, 'height': 950})
        auth = ctx.request.post(BASE + '/api/setup', data={'name': '导出验收', 'email': 'export@example.test', 'password': 'export-test-password', 'demo': False}).json()
        fid = auth['families'][0]['id']
        headers = {'X-CSRF-Token': auth['csrf']}
        def create(kind, data):
            r = ctx.request.post(BASE + f'/api/families/{fid}/records/{kind}', headers=headers, data={'data': data})
            assert r.ok, r.text()
            return r.json()
        people = [create('person', {'name': name, 'branch': '二房' if i == 3 else '长房', 'generation': '第一代' if i < 2 else '第二代', 'gender': 'male' if i == 0 else 'female', 'privacy': 'editors' if i == 4 else 'family', 'bio': '生平测试 <script>window.injected=true</script>', 'birth': {'calendar': 'lunar' if i == 1 else 'solar', 'year': 2024, 'month': 1, 'day': 1}}) for i, name in enumerate(['家长甲', '家长乙', '子女丙', '</script><img src=x onerror=alert(1)>', '私密家人不得导出'])]
        create('relation', {'from_id': people[0]['id'], 'to_id': people[1]['id'], 'type': 'married'})
        for parent in people[:2]:
            create('relation', {'from_id': parent['id'], 'to_id': people[2]['id'], 'type': 'parent'})
        image = Image.new('RGB', (400, 200), '#e84b48')
        image.paste(Image.new('RGB', (200, 200), '#285cea'), (200, 0))
        buffer = io.BytesIO()
        image.save(buffer, 'PNG')
        media = ctx.request.post(BASE + f'/api/families/{fid}/media', headers=headers, multipart={'metadata': json.dumps({'person_ids': [person['id'] for person in people[:2]]}), 'file': {'name': 'shared.png', 'mimeType': 'image/png', 'buffer': buffer.getvalue()}}).json()
        for i, person in enumerate(people[:2]):
            assert ctx.request.post(BASE + f'/api/families/{fid}/media/{media["id"]}/crop', headers=headers, data={'person_id': person['id'], 'x': i, 'size': 1}).ok
            assert ctx.request.put(BASE + f'/api/families/{fid}/records/{person["id"]}', headers=headers, data={'version': 1, 'data': {**person['data'], 'avatar': media['id']}}).ok
        invite = ctx.request.post(BASE + f'/api/families/{fid}/invites?role=viewer', headers=headers).json()['code']
        viewer = browser.new_context(viewport={'width': 635, 'height': 697})
        assert viewer.request.post(BASE + '/api/join', data={'name': '只读家人', 'email': 'viewer-export@example.test', 'password': 'viewer-test-password', 'code': invite}).ok
        page = viewer.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + '/#tree')
        page.wait_for_load_state('networkidle')
        expect(page.locator('.react-flow__node')).to_have_count(4)
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        page.get_by_role('button', name='查看全图', exact=True).click()
        page.wait_for_timeout(300)
        def position_state():
            return page.locator('.react-flow__node').evaluate_all('nodes => nodes.map(n=>[n.dataset.id,n.style.transform])')
        before = position_state()
        viewport_before = page.locator('.react-flow__viewport').get_attribute('style')
        page.get_by_role('button', name='导出', exact=True).click()
        dlg = page.get_by_role('dialog', name='导出世系图谱')
        def download(label, name):
            with page.expect_download(timeout=30000) as pending:
                dlg.get_by_role('button', name=label, exact=False).click()
            path = DATA / name
            pending.value.save_as(path)
            return path
        png = download('PNG 图片', 'family.png')
        svg = download('SVG 图形', 'family.svg')
        html = download('HTML 离线网页', 'family.html')
        assert position_state() == before
        assert page.locator('.react-flow__viewport').get_attribute('style') == viewport_before
        pixels = Image.open(png).convert('RGB')
        assert pixels.width > 635 and pixels.height > 697
        colors = pixels.getcolors(pixels.width * pixels.height)
        assert len(colors) > 100
        assert sum(count for count, (r, g, b) in colors if r > 180 and g < 120 and b < 120) > 100
        assert sum(count for count, (r, g, b) in colors if b > 180 and r < 120) > 100
        text = svg.read_text(encoding='utf-8')
        exported_svg = ET.fromstring(text)
        arrow = next(element for element in exported_svg.iter() if element.get('class') == 'family-direction-arrow')
        expected_fill = page.locator('.family-direction-arrow').first.evaluate('el => getComputedStyle(el).fill')
        assert 'fill: ' + expected_fill in arrow.get('style', '')
        assert '私密家人不得导出' not in text and '/api/' not in text
        assert 'data:image/' in text and 'tree-person-peek' not in text
        assert html.stat().st_size > 1000
        offline_context = browser.new_context(offline=True, viewport={'width': 1280, 'height': 900})
        offline = offline_context.new_page()
        offline.on('pageerror', lambda error: errors.append(str(error)))
        requests = []
        offline.on('request', lambda request: requests.append(request.url) if request.url.startswith(('http:', 'https:')) else None)
        offline.goto(html.as_uri())
        expect(offline.locator('#results button')).to_have_count(4)
        assert offline.locator('#graph').evaluate('image => image.complete && image.naturalWidth > 0')
        expect(offline.locator('#results')).not_to_contain_text('私密家人不得导出')
        offline.get_by_label('查找家人').fill('子女丙')
        offline.locator('#results button').click()
        expect(offline.locator('#detail')).to_contain_text('子女丙')
        expect(offline.locator('#highlight')).to_be_visible()
        before_zoom = offline.locator('#art').get_attribute('style')
        offline.get_by_role('button', name='放大图谱').click()
        assert offline.locator('#art').get_attribute('style') != before_zoom
        offline.get_by_label('查找家人').fill('</script>')
        offline.locator('#results button').click()
        assert not offline.evaluate('window.injected === true')
        expect(offline.locator('#detail img, #detail script')).to_have_count(0)
        assert not requests, requests
        offline.set_viewport_size({'width': 390, 'height': 844})
        assert not offline.evaluate('document.documentElement.scrollWidth > innerWidth')
        offline.screenshot(path=str(DATA / 'offline-mobile.png'), animations='disabled')
        dlg.get_by_role('button', name='完成', exact=True).click()
        page.locator('.tree-display-trigger').click()
        page.get_by_label('图谱房支', exact=True).select_option('长房')
        page.locator('.tree-display-trigger').click()
        page.get_by_role('button', name='关系明细', exact=True).click()
        page.get_by_role('button', name='切换深色模式', exact=True).click()
        page.wait_for_timeout(150)
        page.get_by_role('button', name='导出', exact=True).click()
        filtered = download('HTML 离线网页', 'filtered.html')
        offline.goto(filtered.as_uri())
        expect(offline.locator('#results button')).to_have_count(3)
        assert '</script><img src=x onerror=alert(1)>' not in offline.locator('#results').inner_text()
        expect(offline.locator('header')).to_contain_text('长房 · 关系明细')
        assert not errors, errors
        browser.close()
        print(json.dumps({'passed': True, 'checks': ['full-graph-png-svg-html', 'offscreen-nodes', 'separate-avatar-crops', 'unchanged-layout-viewport', 'viewer-privacy', 'filtered-dark-network', 'offline-search-zoom-mobile', 'html-injection'], 'page_errors': errors}, ensure_ascii=False))
finally:
    server.terminate()
    server.wait(timeout=15)
    log.close()
