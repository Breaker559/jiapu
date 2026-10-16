"""Verify the site directory and registration controls against a disposable SQLite instance."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.request
import uuid

from playwright.sync_api import sync_playwright, expect

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'test-results'
DATA = OUT/('site-admin-'+str(time.time_ns()))
DATA.mkdir(parents=True)
env = {**os.environ, 'QINPU_DATA': str(DATA), 'PYTHONUTF8': '1', 'QINPU_ALLOW_REGISTRATION': '1'}
env.pop('DATABASE_URL', None)
BASE = 'http://127.0.0.1:8883'
PASSWORD = 'admin-browser-test-password'
log = (DATA/'server.log').open('w', encoding='utf-8')


def start():
    process = subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'), '-m', 'uvicorn', 'server.app:app', '--host', '127.0.0.1', '--port', '8883'], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(50):
        try:
            urllib.request.urlopen(BASE+'/api/health', timeout=1)
            return process
        except Exception:
            if process.poll() is not None:
                break
            time.sleep(.2)
    process.terminate()
    process.wait(timeout=15)
    raise RuntimeError('Isolated admin test server did not start')


server = start()
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1050})
        result = context.request.post(BASE+'/api/setup', data={'name': '站点所有者', 'email': 'owner@example.test', 'password': PASSWORD, 'demo': False})
        assert result.ok, result.text()
        owner = result.json()
        visitor = browser.new_context()
        result = visitor.request.post(BASE+'/api/register', data={'name': '林夏', 'email': 'linxia@example.test', 'password': PASSWORD, 'family_name': '林家的记忆'})
        assert result.ok, result.text()
        ordinary = result.json()
        # Fictional fixture accounts make the default 20-row pagination observable.
        with sqlite3.connect(DATA/'qinpu.db') as db:
            stored_hash = db.execute('select password from users where id=?', (owner['user']['id'],)).fetchone()[0]
            for index in range(24):
                db.execute('insert into users(id,email,name,password,recovery,admin) values(?,?,?,?,?,?)',
                           (uuid.uuid4().hex, f'fixture{index:02}@example.test', f'测试账号 {index:02}', stored_hash, 'fixture', 0))
            db.execute('insert into users(id,email,name,password,recovery,admin) values(?,?,?,?,?,?)',
                       (uuid.uuid4().hex, 'standalone@example.test', '独立管理员', stored_hash, 'fixture', 1))
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE+'/#admin')
        page.wait_for_load_state('networkidle')
        expect(page.get_by_role('heading', name='站点管理', exact=True)).to_be_visible()
        expect(page.get_by_role('table').locator('tbody tr')).to_have_count(20)
        expect(page.locator('.admin-pagination')).to_contain_text('共 27 个账号 · 第 1 / 2 页')
        expect(page.locator('.admin-metric').filter(has_text='注册账号').locator('strong')).to_have_text('27')
        page.screenshot(path=str(OUT/'site-admin-desktop.png'), full_page=True)
        page.get_by_role('button', name='下一页', exact=True).click()
        expect(page.get_by_role('table').locator('tbody tr')).to_have_count(7)
        expect(page.locator('.admin-pagination')).to_contain_text('第 2 / 2 页')
        expect(page.get_by_role('button', name='下一页', exact=True)).to_be_disabled()
        page.get_by_label('筛选站点角色').select_option('admin')
        expect(page.get_by_role('table').locator('tbody tr')).to_have_count(2)
        page.get_by_label('筛选站点角色').select_option('all')
        page.get_by_label('搜索账号姓名或邮箱').fill('LINXIA@EXAMPLE')
        page.get_by_role('button', name='搜索', exact=True).click()
        expect(page.get_by_role('table').locator('tbody tr')).to_have_count(1)
        page.get_by_role('button', name='查看账号 linxia@example.test', exact=True).click()
        detail = page.get_by_role('dialog', name='账号详情')
        expect(detail).to_contain_text('林家的记忆')
        expect(detail).to_contain_text('所有者')
        page.screenshot(path=str(OUT/'site-admin-detail.png'), full_page=True)
        detail.get_by_role('button', name='关闭详情').click()
        page.get_by_label('搜索账号姓名或邮箱').fill('没有此用户')
        page.get_by_role('button', name='搜索', exact=True).click()
        expect(page.get_by_text('没有找到账号', exact=True)).to_be_visible()
        page.get_by_role('button', name='清除搜索').click()
        page.get_by_label('每页账号数').select_option('50')
        expect(page.get_by_role('table').locator('tbody tr')).to_have_count(27)
        # Retry must recover after a network failure without retaining stale rows.
        page.route('**/api/admin/users?*', lambda route: route.fulfill(status=503, json={'detail': '测试临时连接失败'}))
        page.get_by_role('button', name='刷新数据').click()
        expect(page.get_by_role('alert')).to_contain_text('测试临时连接失败')
        expect(page.get_by_role('table')).to_have_count(0)
        page.unroute('**/api/admin/users?*')
        page.get_by_role('button', name='重试', exact=True).click()
        expect(page.get_by_role('table').locator('tbody tr')).to_have_count(27)
        page.get_by_role('button', name='关闭公开注册', exact=True).click()
        expect(page.get_by_role('status')).to_contain_text('已关闭公开注册')
        assert context.request.get(BASE+'/api/status').json()['registration_enabled'] is False
        # Check persistence over a real process restart and the logged-out UI.
        server.terminate()
        server.wait(timeout=15)
        server = start()
        page.reload()
        page.wait_for_load_state('networkidle')
        expect(page.get_by_role('button', name='开放公开注册', exact=True)).to_be_visible()
        page.get_by_role('button', name='账号菜单', exact=True).click()
        page.get_by_role('menuitem', name='退出登录', exact=True).click()
        expect(page.get_by_role('button', name='登录家谱', exact=True)).to_be_visible()
        expect(page.get_by_role('button', name='注册账号', exact=True)).to_have_count(0)
        page.get_by_label('登录邮箱', exact=True).fill('owner@example.test')
        page.get_by_label('密码', exact=True).fill(PASSWORD)
        page.get_by_role('button', name='登录家谱', exact=True).click()
        page.get_by_role('button', name='站点管理', exact=True).click()
        page.get_by_role('button', name='开放公开注册', exact=True).click()
        expect(page.get_by_role('status')).to_contain_text('已开放公开注册')
        page.get_by_role('button', name='账号菜单', exact=True).click()
        page.get_by_role('menuitem', name='退出登录', exact=True).click()
        expect(page.get_by_role('button', name='注册账号', exact=True)).to_be_visible()
        # Ordinary family owners see neither the navigation nor any admin data.
        normal = visitor.new_page()
        normal.goto(BASE+'/#admin')
        normal.wait_for_load_state('networkidle')
        expect(normal.get_by_role('button', name='站点管理', exact=True)).to_have_count(0)
        expect(normal.get_by_text('无权访问站点管理', exact=True)).to_be_visible()
        assert visitor.request.get(BASE+'/api/admin/users').status == 403
        assert visitor.request.put(BASE+'/api/admin/registration', data={'enabled': False, 'version': 2}, headers={'X-CSRF-Token': ordinary['csrf']}).status == 403
        assert context.request.get(BASE+'/api/status').json()['registration_enabled'] is True
        # A site administrator need not belong to a family to reach the directory.
        alone_context = browser.new_context()
        assert alone_context.request.post(BASE+'/api/login', data={'email': 'standalone@example.test', 'password': PASSWORD}).ok
        alone = alone_context.new_page()
        alone.goto(BASE)
        alone.wait_for_load_state('networkidle')
        alone.get_by_role('button', name='账号菜单', exact=True).click()
        alone.get_by_role('menuitem', name='修改密码', exact=True).click()
        expect(alone.get_by_role('dialog', name='账号设置')).to_be_visible()
        alone.get_by_role('button', name='取消', exact=True).click()
        alone.get_by_role('button', name='站点管理', exact=True).click()
        expect(alone.get_by_role('heading', name='站点管理', exact=True)).to_be_visible()
        expect(alone.get_by_role('table').locator('tbody tr')).to_have_count(20)
        alone.reload()
        expect(alone.get_by_role('table').locator('tbody tr')).to_have_count(20)
        alone.get_by_role('button', name='账号菜单', exact=True).click()
        expect(alone.get_by_role('menuitem', name='退出登录', exact=True)).to_be_visible()
        alone.keyboard.press('Escape')
        # Mobile navigation, narrow screen, details, and dark theme.
        mobile = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
        assert mobile.request.post(BASE+'/api/login', data={'email': 'owner@example.test', 'password': PASSWORD}).ok
        phone = mobile.new_page()
        phone.on('pageerror', lambda error: errors.append(str(error)))
        phone.goto(BASE)
        phone.wait_for_load_state('networkidle')
        phone.get_by_role('button', name='打开导航', exact=True).tap()
        phone.get_by_role('button', name='站点管理', exact=True).tap()
        expect(phone.get_by_role('table').locator('tbody tr')).to_have_count(20)
        phone.locator('.sidebar').evaluate('(sidebar) => Promise.all(sidebar.getAnimations().map(animation => animation.finished))')
        assert phone.locator('.sidebar').bounding_box()['x'] < 0
        assert phone.evaluate('document.documentElement.scrollWidth') <= 390
        phone.screenshot(path=str(OUT/'site-admin-mobile.png'), full_page=True, animations='disabled')
        phone.get_by_role('button', name='查看账号 linxia@example.test', exact=True).tap()
        expect(phone.get_by_role('dialog', name='账号详情')).to_contain_text('林家的记忆')
        assert phone.evaluate('document.documentElement.scrollWidth') <= 390
        phone.get_by_role('button', name='关闭详情').tap()
        phone.get_by_role('button', name='切换深色模式').tap()
        expect(phone.locator('html')).to_have_attribute('data-mode', 'dark')
        phone.locator('.admin-table-scroll').evaluate('(table) => table.scrollLeft = 0')
        phone.screenshot(path=str(OUT/'site-admin-mobile-dark.png'), full_page=True, animations='disabled')
        phone.set_viewport_size({'width': 360, 'height': 800})
        assert phone.evaluate('document.documentElement.scrollWidth') <= 360
        # The environment-level closure cannot be overridden by the dashboard.
        server.terminate()
        server.wait(timeout=15)
        env['QINPU_ALLOW_REGISTRATION'] = '0'
        server = start()
        alone.reload()
        expect(alone.get_by_role('button', name='开放公开注册', exact=True)).to_be_disabled()
        expect(alone.get_by_text('部署配置已关闭注册', exact=False)).to_be_visible()
        assert not errors, errors
        browser.close()
        print(json.dumps({'passed': True, 'checks': ['directory', 'overview', 'search', 'pagination', 'roles', 'account-details', 'empty-state', 'retry', 'registration-toggle', 'restart-persistence', 'logout-entry', 'family-owner-denial', 'admin-without-family', 'mobile', 'dark-theme', 'environment-closure'], 'errors': errors}, ensure_ascii=False))
finally:
    server.terminate()
    server.wait(timeout=15)
    log.close()
