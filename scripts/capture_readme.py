"""Create GitHub screenshots using fictional records in a disposable database."""
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import expect, sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'test-results' / ('readme-' + str(time.time_ns()))
DATA.mkdir(parents=True)
SHOTS = ROOT / 'docs' / 'images'
SHOTS.mkdir(parents=True, exist_ok=True)
BASE = 'http://127.0.0.1:8887'
env = {**os.environ, 'QINPU_DATA': str(DATA), 'PYTHONUTF8': '1'}
env.pop('DATABASE_URL', None)
log = (DATA / 'server.log').open('w', encoding='utf-8')
server = subprocess.Popen([str(ROOT / '.venv/Scripts/python.exe'), '-m', 'uvicorn', 'server.app:app', '--host', '127.0.0.1', '--port', '8887'], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)


def landscape(palette):
    picture = Image.new('RGB', (1200, 440), palette[0])
    draw = ImageDraw.Draw(picture)
    draw.ellipse((870, 45, 1010, 185), fill=palette[1])
    draw.polygon([(0, 300), (230, 100), (480, 330), (790, 140), (1100, 370), (1200, 290), (1200, 440), (0, 440)], fill=palette[2])
    draw.polygon([(0, 375), (320, 260), (600, 355), (910, 280), (1200, 380), (1200, 440), (0, 440)], fill=palette[3])
    draw.line((0, 405, 1200, 405), fill=palette[0], width=4)
    buffer = io.BytesIO()
    picture.save(buffer, 'PNG')
    return buffer.getvalue()


try:
    for _ in range(50):
        try:
            urllib.request.urlopen(BASE + '/api/health', timeout=1)
            break
        except Exception:
            time.sleep(.2)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        ctx = browser.new_context(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
        auth = ctx.request.post(BASE + '/api/setup', data={'name': '演示管理员', 'email': 'demo@example.test', 'password': 'readme-demo-password', 'demo': True}).json()
        fid = auth['families'][0]['id']
        headers = {'X-CSRF-Token': auth['csrf']}
        records = ctx.request.get(BASE + f'/api/families/{fid}/state').json()['records']
        people = [record for record in records if record['kind'] == 'person']
        attachments = []
        for title, palette in [('故乡山色 · 示例插画', ['#dcece6', '#f1d297', '#93b8a7', '#598d80']), ('秋日相聚 · 示例插画', ['#ede8df', '#e3b779', '#b3aaa0', '#788f86'])]:
            result = ctx.request.post(BASE + f'/api/families/{fid}/media', headers=headers, multipart={'metadata': json.dumps({'title': title, 'album': '我们的故乡', 'description': '文档演示用程序绘制插画，不是真实家庭照片。', 'person_ids': [people[0]['id']]}), 'file': {'name': title + '.png', 'mimeType': 'image/png', 'buffer': landscape(palette)}})
            assert result.ok, result.text()
            attachments.append(result.json())
        clip = DATA / '相聚片段.mp4'
        subprocess.run([str(ROOT / '.venv/Scripts/python.exe'), str(ROOT / 'scripts/qa_media_fixture.py'), str(clip)], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        response = ctx.request.post(BASE + f'/api/families/{fid}/media', headers=headers, multipart={'metadata': json.dumps({'title': '相聚片段 · 示例视频', 'album': '我们的故乡'}), 'file': {'name': clip.name, 'mimeType': 'video/mp4', 'buffer': clip.read_bytes()}})
        assert response.ok, response.text()
        body = f'## 把故乡的记忆留下来\n\n一张旧照片，一段长辈的讲述，让一家人的故事慢慢完整。\n\n![故乡山色 · 演示插画](media:{attachments[0]["id"]})\n\n### 这次一起整理\n\n- **记录名字**：请长辈辨认照片中的家人。\n- **保留原文**：日期和地点记不清，就先写下线索。\n- **分享回忆**：图片与视频都能插入家族档案。\n\n> 把相聚的时光，留给未来的我们。'
        response = ctx.request.post(BASE + f'/api/families/{fid}/records/story', headers=headers, data={'data': {'title': '故乡与相聚的时光', 'body': body, 'format': 'markdown', 'category': '家族故事', 'source': '文档演示资料，人物、事件与画面均为虚构。'}})
        assert response.ok, response.text()
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        def shot(filename, full=False):
            page.wait_for_load_state('networkidle')
            page.screenshot(path=str(SHOTS / filename), full_page=full, animations='disabled')
            with Image.open(SHOTS / filename) as image:
                image.save(SHOTS / filename, optimize=True)
        page.goto(BASE + '/#tree')
        page.wait_for_load_state('networkidle')
        page.get_by_role('button', name='查看全图', exact=True).click()
        page.wait_for_timeout(300)
        shot('tree.png')
        page.get_by_role('button', name='导出', exact=True).click()
        shot('tree-export.png')
        with page.expect_download() as download:
            page.get_by_role('dialog').get_by_role('button', name='HTML 离线网页', exact=False).click()
        html = DATA / '家谱示例.html'
        download.value.save_as(html)
        page.get_by_role('dialog').get_by_role('button', name='完成', exact=True).click()
        page.get_by_role('button', name='家族首页', exact=True).click()
        shot('home.png', True)
        page.get_by_role('button', name='家族相册', exact=True).click()
        shot('memories.png')
        page.get_by_role('button', name='家族档案', exact=True).click()
        page.locator('.story-card').filter(has_text='故乡与相聚的时光').click()
        shot('markdown.png')
        page.get_by_role('dialog').get_by_role('button', name='关闭', exact=True).click()
        page.get_by_role('button', name='家族成员', exact=True).click()
        page.locator('.member-card').filter(has_text='林淑华').click()
        shot('birthday.png')
        page.set_viewport_size({'width': 390, 'height': 844})
        shot('mobile.png')
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.goto(html.as_uri())
        page.get_by_label('查找家人').fill('林淑华')
        page.locator('#results button').click()
        shot('offline.png')
        assert not errors, errors
        browser.close()
        print(json.dumps({'screenshots': [path.name for path in SHOTS.glob('*.png')], 'source': 'fictional demo in disposable database', 'bytes': sum(path.stat().st_size for path in SHOTS.glob('*.png'))}, ensure_ascii=False))
finally:
    server.terminate()
    server.wait(timeout=15)
    log.close()
