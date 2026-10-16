"""Markdown, mixed media and birthday UI acceptance in an isolated family."""
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.sync_api import expect, sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'test-results'
OUT.mkdir(exist_ok=True)
DATA = OUT / ('story-media-' + str(time.time_ns()))
DATA.mkdir()
BASE = 'http://127.0.0.1:8885'
photo, video, markdown = DATA / '团圆.png', DATA / '旅行.mp4', DATA / '团圆记忆.md'
Image.new('RGB', (720, 420), '#95b9a5').save(photo)
subprocess.run([str(ROOT / '.venv/Scripts/python.exe'), str(ROOT / 'scripts/qa_media_fixture.py'), str(video)], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
markdown.write_text('## 那年的团圆\n\n我们一起留下了 **珍贵记忆**。\n\n| 地点 | 日期 |\n| --- | --- |\n| 故乡 | 中秋 |\n\n<script>window.markdownExecuted=true</script>\n\n[测试链接](javascript:alert(1))\n\n![外站图片](https://example.invalid/tracker.png)\n', encoding='utf-8')
env = {**os.environ, 'QINPU_DATA': str(DATA), 'PYTHONUTF8': '1'}
env.pop('DATABASE_URL', None)
log = (DATA / 'server.log').open('w', encoding='utf-8')
server = subprocess.Popen([str(ROOT / '.venv/Scripts/python.exe'), '-m', 'uvicorn', 'server.app:app', '--host', '127.0.0.1', '--port', '8885'], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)


def playback(page, locator):
    expect(locator).to_be_visible()
    locator.evaluate('(video) => { video.muted = true; return video.play(); }')
    page.wait_for_function('() => [...document.querySelectorAll("video")].some(v => v.currentTime > 0.15 && v.videoWidth === 320)')
    locator.evaluate('(video) => video.pause()')


try:
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE + '/api/health', timeout=1)
            break
        except Exception:
            time.sleep(.25)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors, external = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: external.append(request.url) if 'example.invalid' in request.url else None)
        result = page.request.post(BASE + '/api/setup', data={'name': '验收用户', 'email': 'media@example.test', 'password': 'media-test-password', 'demo': False})
        assert result.ok, result.text()
        account = result.json()
        fid = account['families'][0]['id']
        for name, calendar, month, day in [('农历家人', 'lunar', 1, 1), ('阳历家人', 'solar', 2, 10)]:
            response = page.request.post(BASE + f'/api/families/{fid}/records/person', headers={'X-CSRF-Token': account['csrf']}, data={'data': {'name': name, 'birth': {'calendar': calendar, 'year': 2024, 'month': month, 'day': day}}})
            assert response.ok, response.text()
        page.goto(BASE)
        page.get_by_role('button', name='上传图片 / 视频', exact=True).first.click()
        dlg = page.get_by_role('dialog')
        dlg.locator('input[type=file]').set_input_files([str(photo), str(video)])
        dlg.get_by_label('关联人物', exact=True).select_option(label='农历家人')
        dlg.get_by_role('button', name='上传 / 重试').click()
        expect(dlg.get_by_text('2 / 2 个文件已完成', exact=True)).to_be_visible(timeout=30000)
        dlg.get_by_role('button', name='完成', exact=True).click()
        expect(page.locator('.home-photos .media-thumbnail')).to_have_count(2)
        expect(page.get_by_role('button', name='上传图片 / 视频', exact=True)).to_be_visible()
        page.locator('.home-photos button').filter(has_text='旅行.mp4').click()
        playback(page, dlg.locator('video'))
        expect(dlg.get_by_role('button', name='设为头像')).to_have_count(0)
        with page.expect_download() as download:
            dlg.get_by_role('button', name='原视频', exact=True).click()
        destination = DATA / 'download.mp4'
        download.value.save_as(destination)
        assert destination.read_bytes() == video.read_bytes()
        dlg.get_by_role('button', name='关闭', exact=True).click()
        page.get_by_role('button', name='家族相册', exact=True).click()
        expect(page.locator('.album-card')).to_have_count(2)
        expect(page.locator('.album-card .media-play')).to_have_count(1)
        page.screenshot(path=str(OUT / 'mixed-media-desktop.png'), full_page=True, animations="disabled")

        page.get_by_role('button', name='家族档案', exact=True).click()
        page.get_by_role('button', name='记录故事', exact=True).click()
        dlg.get_by_label('导入 Markdown 文件', exact=True).set_input_files(str(markdown))
        expect(dlg.get_by_label('标题 *', exact=True)).to_have_value('团圆记忆')
        editor = dlg.get_by_label('正文', exact=True)
        editor.focus()
        editor.press('Control+End')
        dlg.get_by_label('上传文章图片或视频', exact=True).set_input_files(str(photo))
        expect(editor).to_be_enabled(timeout=30000)
        select = dlg.get_by_label('选择已有媒体插入正文', exact=True)
        select.select_option(label='视频 · 旅行.mp4')
        dlg.get_by_role('button', name='插入正文', exact=True).click()
        source = editor.input_value()
        assert source.count('](media:') == 2
        assert '![外站图片](https://example.invalid/tracker.png)' in source
        dlg.get_by_role('button', name='预览文章', exact=True).click()
        preview = dlg.get_by_label('文章预览', exact=True)
        expect(preview.get_by_role('heading', name='那年的团圆')).to_be_visible()
        expect(preview.locator('table')).to_have_count(1)
        expect(preview.locator('.story-media img')).to_have_count(1)
        playback(page, preview.locator('video'))
        expect(preview.locator('.story-media-missing')).to_contain_text('外站图片')
        assert not page.evaluate('window.markdownExecuted === true')
        assert not preview.locator('script, a[href^="javascript:"]').count()
        assert not external, external
        page.screenshot(path=str(OUT / 'markdown-editor-desktop.png'), full_page=True, animations="disabled")
        dlg.get_by_role('button', name='保存档案', exact=True).click()
        expect(dlg).not_to_be_visible()
        page.reload()
        card = page.locator('.story-card').filter(has_text='团圆记忆')
        assert 'media:' not in card.inner_text() and '<script>' not in card.inner_text()
        card.click()
        expect(dlg.locator('.story-markdown strong')).to_have_text('珍贵记忆')
        playback(page, dlg.locator('video'))
        with page.expect_download() as download:
            dlg.get_by_role('button', name='导出 .md', exact=True).click()
        destination = DATA / 'export.md'
        download.value.save_as(destination)
        assert destination.read_text(encoding='utf-8') == source
        page.screenshot(path=str(OUT / 'markdown-reader-desktop.png'), full_page=True, animations="disabled")
        page.set_viewport_size({'width': 390, 'height': 844})
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        assert dlg.evaluate('(el) => el.scrollWidth <= el.clientWidth')
        page.screenshot(path=str(OUT / 'markdown-reader-mobile.png'), full_page=True, animations="disabled")
        dlg.get_by_role('button', name='关闭', exact=True).click()
        page.set_viewport_size({'width': 1440, 'height': 1000})
        page.get_by_role('button', name='切换深色模式', exact=True).click()
        page.locator('.story-card').filter(has_text='团圆记忆').click()
        page.screenshot(path=str(OUT / 'markdown-reader-dark.png'), full_page=True, animations="disabled")
        dlg.get_by_role('button', name='关闭', exact=True).click()
        page.get_by_role('button', name='切换浅色模式', exact=True).click()

        # Reproduce editing pre-Markdown demo archives as well as saved plain text.
        greeting = '## 你好\n一张照片、一段口述、一个熟悉的名字，都是家族故事的起点。\n\n试着从一位你熟悉的长辈开始，补充他的经历，邀请家人一起留下记忆。此处内容为产品演示，可在创建自己的家族后修改。'
        for title, legacy in [('未指定格式的旧档案', True), ('已保存为纯文本的档案', False)]:
            response = page.request.post(BASE + f'/api/families/{fid}/records/story', headers={'X-CSRF-Token': account['csrf']}, data={'data': {'title': title, 'body': greeting, 'format': 'plain'}})
            assert response.ok, response.text()
            row = response.json()
            if legacy:
                # Only touch this test's disposable database to emulate old seed data.
                row['data'].pop('format')
                with sqlite3.connect(DATA / 'qinpu.db') as db:
                    db.execute('UPDATE records SET data=? WHERE id=?', (json.dumps(row['data']), row['id']))
            page.reload()
            card = page.locator('.story-card').filter(has_text=title)
            card.click()
            dlg.get_by_role('button', name='编辑档案', exact=True).click()
            expect(dlg.get_by_label('正文格式', exact=True)).to_have_value('markdown' if legacy else 'plain')
            dlg.get_by_label('正文', exact=True).fill(greeting)
            dlg.get_by_role('button', name='预览文章', exact=True).click()
            if not legacy:
                # An explicit plain choice must still survive preview, save and reload.
                expect(dlg.get_by_label('文章预览').locator('.prose')).to_have_text(greeting)
                expect(dlg.get_by_role('button', name='切换为 Markdown', exact=True)).to_be_visible()
                dlg.get_by_role('button', name='保存档案', exact=True).click()
                expect(dlg).not_to_be_visible()
                page.reload()
                card.click()
                expect(dlg.locator('.prose')).to_have_text(greeting)
                dlg.get_by_role('button', name='编辑档案', exact=True).click()
                dlg.get_by_role('button', name='切换为 Markdown', exact=True).click()
                expect(dlg.get_by_label('正文', exact=True)).to_have_value(greeting)
                dlg.get_by_role('button', name='预览文章', exact=True).click()
            expect(dlg.get_by_label('文章预览').get_by_role('heading', name='你好', level=2, exact=True)).to_be_visible()
            dlg.get_by_role('button', name='保存档案', exact=True).click()
            expect(dlg).not_to_be_visible()
            page.reload()
            assert '##' not in card.inner_text()
            card.click()
            expect(dlg.get_by_role('heading', name='你好', level=2, exact=True)).to_be_visible()
            dlg.get_by_role('button', name='编辑档案', exact=True).click()
            expect(dlg.get_by_label('正文格式', exact=True)).to_have_value('markdown')
            expect(dlg.get_by_label('正文', exact=True)).to_have_value(greeting)
            dlg.get_by_role('button', name='取消', exact=True).click()
        page.get_by_role('button', name='家族书', exact=True).click()
        expect(page.locator('.book-story').get_by_role('heading', name='你好', level=2, exact=True)).to_have_count(2)
        page.get_by_role('button', name='家族成员', exact=True).click()
        for name, primary, secondary in [('农历家人', '2024年正月初一', '阳历 2024-02-10'), ('阳历家人', '2024.02.10', '农历 2024年正月初一')]:
            page.locator('.member-card').filter(has_text=name).click()
            birthday = dlg.locator('.profile-birthday')
            expect(birthday.locator('strong')).to_contain_text(primary)
            expect(birthday.locator('small')).to_have_text(secondary)
            assert birthday.locator('strong').evaluate('el => parseFloat(getComputedStyle(el).fontSize)') > birthday.locator('small').evaluate('el => parseFloat(getComputedStyle(el).fontSize)')
            page.screenshot(path=str(OUT / ('birthday-' + name + '.png')), full_page=True, animations="disabled")
            dlg.get_by_role('button', name='关闭', exact=True).click()
        page.get_by_role('button', name='家族首页', exact=True).click()
        page.locator('.home-photos').scroll_into_view_if_needed()
        page.screenshot(path=str(OUT / 'memories-home.png'), full_page=True, animations="disabled")
        assert not errors, errors
        browser.close()
        print(json.dumps({'passed': True, 'checks': ['home-mixed-upload', 'video-playback-and-download', 'gallery-posters', 'markdown-import-upload-preview-save-reload-export', 'legacy-markdown-edit-read-excerpt-book', 'explicit-plain-preserved-and-convertible', 'safe-markdown', 'mobile-dark', 'primary-calendar-birthday'], 'page_errors': errors}, ensure_ascii=False))
except Exception:
    if 'page' in locals():
        try:
            page.screenshot(path=str(OUT / 'story-media-failure.png'), full_page=True, animations="disabled")
        except Exception:
            pass
    raise
finally:
    server.terminate()
    server.wait(timeout=15)
    log.close()
