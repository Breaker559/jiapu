"""Exercise layout gestures against a disposable family; never touch real family data."""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'test-results'
DATA = OUT / ('tree-arrangement-' + str(time.time_ns()))
DATA.mkdir(parents=True)
env = {**os.environ, 'QINPU_DATA': str(DATA), 'PYTHONUTF8': '1'}
env.pop('DATABASE_URL', None)
log = (DATA / 'server.log').open('w', encoding='utf-8')
server = subprocess.Popen([str(ROOT / '.venv/Scripts/python.exe'), '-m', 'uvicorn', 'server.app:app', '--host', '127.0.0.1', '--port', '8881'], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
BASE = 'http://127.0.0.1:8881'
try:
    for _ in range(50):
        try:
            urllib.request.urlopen(BASE + '/api/health', timeout=1)
            break
        except Exception:
            time.sleep(.2)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        ctx = browser.new_context(viewport={'width': 1680, 'height': 1200})
        response = ctx.request.post(BASE + '/api/setup', data={'name': '排版验收', 'email': 'layout@example.test', 'password': 'layout-test-password', 'demo': False})
        assert response.ok, response.text()
        auth = response.json()
        fid = auth['families'][0]['id']
        headers = {'X-CSRF-Token': auth['csrf']}
        def create(kind, data):
            r = ctx.request.post(f'{BASE}/api/families/{fid}/records/{kind}', data={'data': data}, headers=headers)
            assert r.ok, r.text()
            return r.json()
        people = [create('person', {'name': name, 'gender': gender, 'generation': '第一代' if i < 2 else '第二代', 'branch': '长房' if i < 4 else '二房'}) for i, (name, gender) in enumerate([('顾言', 'male'), ('林夏', 'female'), ('顾小满', 'male'), ('顾星河', 'female'), ('顾清和', 'male')])]
        create('relation', {'from_id': people[0]['id'], 'to_id': people[1]['id'], 'type': 'married'})
        for child in people[2:]:
            for parent in people[:2]:
                create('relation', {'from_id': parent['id'], 'to_id': child['id'], 'type': 'parent'})
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + '/#tree')
        page.wait_for_load_state('networkidle')
        expect(page.get_by_role('toolbar', name='图谱排版工具')).to_be_visible()
        expect(page.locator('.react-flow__node')).to_have_count(5)
        page.screenshot(path=str(OUT / 'tree-arrangement-initial.png'), full_page=True)
        def node(i):
            return page.locator(f'.react-flow__node[data-id="{people[i]["id"]}"]')
        def positions():
            return page.locator('.react-flow__node').evaluate_all('nodes => Object.fromEntries(nodes.map(n => {const m = new DOMMatrix(n.style.transform); return [n.dataset.id, {x:m.e,y:m.f}]}))')
        def zoom():
            return page.locator('.react-flow__viewport').evaluate('n => new DOMMatrix(getComputedStyle(n).transform).a')
        def settle():
            page.wait_for_timeout(120)
        def drag(i, dx, dy, finish=True):
            box = node(i).bounding_box()
            x, y = box['x'] + 24 * zoom(), box['y'] + 30 * zoom()
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + dx * zoom(), y + dy * zoom(), steps=12)
            if finish:
                page.mouse.up()
                settle()
        def clear():
            page.get_by_role('button', name='取消选择', exact=True).click()
        def select(indices):
            if page.get_by_role('button', name='取消选择', exact=True).count() and page.get_by_role('button', name='取消选择', exact=True).is_enabled():
                clear()
            for i in indices:
                node(i).locator('.tree-person-main').click(modifiers=['Control'])
            expect(page.locator('.react-flow__node.selected')).to_have_count(len(indices))
        def same(a, b):
            return a.keys() == b.keys() and all(abs(a[k][axis] - b[k][axis]) < .02 for k in a for axis in ('x', 'y'))
        initial = positions()
        expect(page.get_by_role('button', name='左对齐', exact=True)).to_have_count(0)
        expect(page.get_by_role('button', name='撤销排版', exact=True)).to_be_disabled()

        # Shift marquee from move mode; partial card intersection selects the three children.
        boxes = [node(i).bounding_box() for i in (2, 3, 4)]
        left = min(b['x'] for b in boxes) - 8
        right = max(b['x'] + b['width'] for b in boxes) + 8
        top = min(b['y'] for b in boxes) - 8
        bottom = max(b['y'] + b['height'] / 2 for b in boxes)
        page.keyboard.down('Shift')
        page.mouse.move(left, top)
        page.mouse.down()
        page.mouse.move(right, bottom, steps=15)
        page.mouse.up()
        page.keyboard.up('Shift')
        expect(page.locator('.react-flow__node.selected')).to_have_count(3)
        expect(page.locator('.tree-selection-count')).to_have_text('已选 3 人')
        expect(page.get_by_role('dialog')).to_have_count(0)
        page.get_by_role('button', name='框选', exact=True).click()
        before = positions()
        # Grab the selection rectangle; the group must preserve every internal offset.
        group = page.locator('.react-flow__nodesselection-rect').bounding_box()
        x, y = group['x'] + group['width'] / 2, group['y'] + 10
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 27, y + 30, steps=12)
        page.mouse.up()
        settle()
        after = positions()
        deltas = [(after[people[i]['id']]['x'] - before[people[i]['id']]['x'], after[people[i]['id']]['y'] - before[people[i]['id']]['y']) for i in (2, 3, 4)]
        assert abs(deltas[0][0]) > 10 and all(abs(dx - deltas[0][0]) < .02 and abs(dy - deltas[0][1]) < .02 for dx, dy in deltas), deltas
        assert all(after[people[i]['id']] == before[people[i]['id']] for i in (0, 1))
        page.get_by_role('button', name='撤销排版', exact=True).click()
        assert same(positions(), before)
        page.get_by_role('button', name='重做排版', exact=True).click()
        assert same(positions(), after)
        clear()

        # Snap within eight screen pixels and draw a horizontal guide; disabling restores precision.
        page.get_by_role('button', name='一键排版', exact=True).click()
        page.wait_for_timeout(400)
        select([2])
        drag(2, 23, 5, finish=False)
        expect(page.locator('.tree-snap-guides line[data-axis="y"]')).to_have_count(1)
        page.screenshot(path=str(OUT / 'tree-arrangement-snapping.png'), full_page=True)
        page.mouse.up()
        settle()
        pos = positions()
        assert abs(pos[people[2]['id']]['y'] - pos[people[3]['id']]['y']) < .02
        expect(page.locator('.tree-snap-guides line')).to_have_count(0)
        page.get_by_role('button', name='吸附', exact=False).click()
        before = positions()
        drag(2, 20, 14, finish=False)
        expect(page.locator('.tree-snap-guides line')).to_have_count(0)
        page.mouse.up()
        settle()
        assert positions()[people[2]['id']]['y'] > before[people[2]['id']]['y'] + 10

        # Every alignment affects only selected cards, then undo restores the exact arrangement.
        select([2, 3, 4])
        for label, axis in [('左对齐', 'x'), ('水平居中', 'x'), ('右对齐', 'x'), ('顶部对齐', 'y'), ('垂直居中', 'y'), ('底部对齐', 'y')]:
            before = positions()
            page.get_by_role('button', name=label, exact=True).click()
            settle()
            current = positions()
            values = [current[people[i]['id']][axis] for i in (2, 3, 4)]
            assert max(values) - min(values) < .02, (label, values)
            assert all(current[people[i]['id']] == before[people[i]['id']] for i in (0, 1))
            page.get_by_role('button', name='撤销排版', exact=True).click()
            assert same(positions(), before), label
        for label, axis, size in [('水平等距', 'x', 256), ('垂直等距', 'y', 132)]:
            before = positions()
            page.get_by_role('button', name=label, exact=True).click()
            settle()
            values = sorted(positions()[people[i]['id']][axis] for i in (2, 3, 4))
            assert abs(values[2] - values[1] - (values[1] - values[0])) < .02 and values[1] - values[0] >= size + 24 - .02
            page.get_by_role('button', name='撤销排版', exact=True).click()
            assert same(positions(), before)
        expect(page.get_by_role('dialog')).to_have_count(0)

        # Labels sit beside their terminal lines, follow drags, and remain clickable.
        clear()
        for i in (2, 3, 4):
            card = node(i).bounding_box()
            label = page.locator(f'.family-kinship-label[data-person="{people[i]["id"]}"] .react-flow__edge-textbg').bounding_box()
            assert label['x'] > card['x'] + card['width'] / 2 + 5 * zoom()
            assert label['y'] + label['height'] < card['y']
        page.locator(f'.family-kinship-label[data-person="{people[3]["id"]}"] .react-flow__edge-textwrapper').click()
        expect(page.get_by_role('dialog', name='这组家人的关系')).to_be_visible()
        page.get_by_role('dialog').get_by_role('button', name='关闭', exact=True).last.click()
        page.get_by_role('button', name='关系明细', exact=True).click()
        settle()
        labels = []
        for edge in page.locator('.react-flow__edge-parent').all():
            label = edge.locator('.react-flow__edge-textbg').bounding_box()
            labels.append(label)
            points = edge.evaluate('e => {const p=e.querySelector(".react-flow__edge-path"),m=p.getScreenCTM(),points=[];for(let i=0;i<=p.getTotalLength();i+=2){const q=p.getPointAtLength(i).matrixTransform(m);points.push({x:q.x,y:q.y})}return points}')
            assert not any(label['x'] < q['x'] < label['x'] + label['width'] and label['y'] < q['y'] < label['y'] + label['height'] for q in points), 'title straddles its own line'
        for i, a in enumerate(labels):
            for b in labels[i + 1:]:
                assert a['x'] + a['width'] <= b['x'] or b['x'] + b['width'] <= a['x'] or a['y'] + a['height'] <= b['y'] or b['y'] + b['height'] <= a['y'], 'different parent labels overlap'
        page.get_by_role('button', name='家庭树', exact=True).click()
        saved = positions()
        page.reload()
        page.wait_for_load_state('networkidle')
        assert same(positions(), saved), 'refresh lost layout'

        # One-click layout is deterministic and undoable, including from a restored layout.
        page.get_by_role('button', name='一键排版', exact=True).click()
        page.wait_for_timeout(400)
        assert same(positions(), initial), 'automatic layout differs'
        page.get_by_role('button', name='撤销排版', exact=True).click()
        assert same(positions(), saved)
        page.get_by_role('button', name='显示设置', exact=True).click()
        page.get_by_label('图谱房支').select_option('长房')
        expect(page.locator('.react-flow__node')).to_have_count(4)
        page.get_by_label('图谱房支').select_option('')
        page.get_by_role('button', name='显示设置', exact=True).click()
        expect(page.locator('.react-flow__node')).to_have_count(5)
        settle()
        assert same(positions(), saved), 'filter scope lost full layout'

        # Shortcut scope and keyboard movement; no accidental person modal during multiselection.
        page.get_by_role('button', name='框选', exact=True).click()
        page.locator('.tree-wrap').focus()
        page.keyboard.press('Control+a')
        expect(page.locator('.react-flow__node.selected')).to_have_count(5)
        page.keyboard.press('Escape')
        expect(page.locator('.react-flow__node.selected')).to_have_count(0)
        select([2, 3])
        select([2])
        before = positions()
        node(2).focus()
        page.keyboard.press('ArrowRight')
        settle()
        assert abs(positions()[people[2]['id']]['x'] - before[people[2]['id']]['x'] - 5) < .02
        page.keyboard.press('Control+z')
        assert same(positions(), before)
        page.keyboard.press('Control+Shift+z')
        assert not same(positions(), before)
        page.get_by_role('button', name='一键排版', exact=True).click()
        page.wait_for_timeout(400)
        clear()
        page.screenshot(path=str(OUT / 'tree-arrangement-desktop.png'), full_page=True)

        # The explicit marquee tool works without a modifier, including after zooming.
        page.locator('.react-flow__controls-zoomout').click()
        page.wait_for_timeout(250)
        boxes = [node(i).bounding_box() for i in (2, 3)]
        page.mouse.move(min(b['x'] for b in boxes) - 8, min(b['y'] for b in boxes) - 8)
        page.mouse.down()
        page.mouse.move(max(b['x'] + b['width'] for b in boxes) + 8, max(b['y'] + b['height'] / 2 for b in boxes), steps=15)
        page.mouse.up()
        expect(page.locator('.react-flow__node.selected')).to_have_count(2)
        clear()
        select([2])
        # Reload restored the default 'on' state; six screen pixels must still snap at this zoom.
        drag(2, 23, 6 / zoom(), finish=False)
        expect(page.locator('.tree-snap-guides line[data-axis="y"]')).to_have_count(1)
        guide = page.locator('.tree-snap-guides line[data-axis="y"]').bounding_box()
        card = node(3).bounding_box()
        assert min(abs(guide['y'] - y) for y in [card['y'], card['y'] + card['height'] / 2, card['y'] + card['height']]) < 1
        page.mouse.up()
        settle()
        clear()
        # Holding Space pans in marquee mode without moving any people or drawing a selection.
        before = positions()
        viewport_before = page.locator('.react-flow__viewport').get_attribute('style')
        canvas = page.locator('.tree-canvas').bounding_box()
        page.keyboard.down('Space')
        page.mouse.move(canvas['x'] + 25, canvas['y'] + 50)
        page.mouse.down()
        page.mouse.move(canvas['x'] + 75, canvas['y'] + 80, steps=10)
        page.mouse.up()
        page.keyboard.up('Space')
        settle()
        assert same(positions(), before)
        assert page.locator('.react-flow__viewport').get_attribute('style') != viewport_before
        expect(page.locator('.react-flow__node.selected')).to_have_count(0)

        # Narrow and touch layouts must fit without horizontal overflow.
        mobile = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, storage_state=ctx.storage_state())
        phone = mobile.new_page()
        phone.on('pageerror', lambda error: errors.append(str(error)))
        phone.goto(BASE + '/#tree')
        phone.wait_for_load_state('networkidle')
        assert not phone.evaluate('document.documentElement.scrollWidth > innerWidth')
        phone.get_by_role('button', name='框选', exact=True).tap()
        phone.get_by_role('button', name='全选', exact=True).tap()
        expect(phone.locator('.tree-selection-count')).to_have_text('已选 5 人')
        phone.screenshot(path=str(OUT / 'tree-arrangement-mobile.png'), full_page=True)
        phone.get_by_role('button', name='切换深色模式').tap()
        phone.screenshot(path=str(OUT / 'tree-arrangement-dark-mobile.png'), full_page=True)
        assert not errors, errors
        browser.close()
        print(json.dumps({'passed': True, 'checks': ['marquee', 'group-drag', 'snap-guides', 'snap-toggle', 'six-alignments', 'two-distributions', 'side-labels-in-both-views', 'label-click', 'undo-redo', 'auto-layout', 'reload-persistence', 'filter-scopes', 'keyboard', 'touch-toolbar', 'mobile-dark'], 'errors': errors}, ensure_ascii=False))
finally:
    server.terminate()
    server.wait(timeout=15)
    log.close()
