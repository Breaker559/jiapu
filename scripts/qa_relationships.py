"""Exercise complex families in an isolated server; never write to the user's database."""
import os,sys,json,time,subprocess,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'test-results';OUT.mkdir(exist_ok=True)
DATA=OUT/('relations-data-'+str(time.time_ns()));DATA.mkdir()
env={**os.environ,'QINPU_DATA':str(DATA),'PYTHONUTF8':'1'};env.pop('DATABASE_URL',None)
log=(DATA/'server.log').open('w',encoding='utf-8')
server=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),'-m','uvicorn','server.app:app','--host','127.0.0.1','--port','8879'],cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
BASE='http://127.0.0.1:8879'
try:
    for _ in range(40):
        try:urllib.request.urlopen(BASE+'/api/health',timeout=1);break
        except Exception:time.sleep(.25)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1100})
        setup=context.request.post(BASE+'/api/setup',data={'name':'关系测试','email':'relations@example.test','password':'relations-test-password','demo':False})
        assert setup.ok,setup.text()
        auth=setup.json();fid=auth['families'][0]['id'];headers={'X-CSRF-Token':auth['csrf']}
        def create(kind,data):
            r=context.request.post(f'{BASE}/api/families/{fid}/records/{kind}',data={'data':data},headers=headers)
            assert r.ok,r.text()
            return r.json()
        persons=[create('person',{'name':n,'gender':gender}) for n,gender in [('顾言','male'),('林夏','female'),('周宁','female'),('顾小满','male'),('顾星河','female'),('叶棠','male')]]
        def link(a,b,kind):return create('relation',{'from_id':persons[a]['id'],'to_id':persons[b]['id'],'type':kind})
        legacy=link(0,1,'spouse');marriage=link(0,2,'married')
        for a,b,kind in [(0,3,'parent'),(1,3,'parent'),(0,4,'parent'),(2,4,'parent'),(2,3,'step'),(5,3,'adoptive')]:link(a,b,kind)
        page=context.new_page();errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/#tree');page.wait_for_load_state('networkidle')
        expect(page.locator('.react-flow__node')).to_have_count(6)
        marriage_edge=page.locator(f'.react-flow__edge[data-id="{marriage["id"]}"]')
        expect(marriage_edge.locator('.react-flow__edge-text')).to_have_text('妻')
        expect(page.get_by_role('button',name='家庭树',exact=True)).to_have_attribute('aria-pressed','true')
        expect(page.locator('.react-flow__edge-text').filter(has_text='亲生')).to_have_count(0)
        # Correct a legacy combined relationship from its visible edge.
        legacy_edge=page.locator(f'.react-flow__edge[data-id="{legacy["id"]}"]')
        legacy_edge.locator('.react-flow__edge-textwrapper').click()
        expect(page.get_by_role('dialog')).to_contain_text('配偶 / 伴侣（待细分）')
        page.get_by_role('button',name='编辑关系',exact=True).click()
        dlg=page.get_by_role('dialog');dlg.get_by_label('关系类型',exact=True).select_option('coparent')
        expect(dlg.get_by_text('仅表示共同承担育儿责任',exact=False)).to_be_visible()
        dlg.get_by_label('核实状态',exact=True).select_option('uncertain')
        dlg.get_by_label('关系备注',exact=True).fill('仅共同照顾顾小满；是否存在其他关系仍需核实。')
        dlg.get_by_label('资料来源',exact=True).fill('家人口述，待复核')
        dlg.get_by_role('button',name='保存关系',exact=True).click();expect(dlg).not_to_be_visible()
        expect(legacy_edge).to_contain_text('共同育儿 · 待核实')
        # Add another relationship without implying any new parentage.
        page.get_by_role('button',name='连接亲属',exact=True).click()
        dlg=page.get_by_role('dialog');dlg.get_by_label('关系类型',exact=True).select_option('former_partner')
        dlg.get_by_label('一方',exact=True).select_option(persons[1]['id'])
        dlg.get_by_label('另一方',exact=True).select_option(persons[5]['id'])
        dlg.get_by_role('button',name='保存关系',exact=True).click();expect(dlg).not_to_be_visible()
        page.wait_for_load_state('networkidle')
        rows=context.request.get(f'{BASE}/api/families/{fid}/state').json()['records']
        relations=[r for r in rows if r['kind']=='relation']
        assert len(relations)==9
        assert len([r for r in relations if r['data']['type'] in ['parent','adoptive','step']])==6
        # The default tree aggregates parent records, but exposes every original relation.
        expect(page.locator('.react-flow__edge-family')).to_have_count(2)
        page.get_by_role('button',name='显示设置',exact=True).click()
        expect(page.get_by_label('显示称谓',exact=True)).to_be_checked()
        page.get_by_role('button',name='显示设置',exact=True).click()
        expect(page.locator(f'.family-kinship-label[data-person="{persons[3]["id"]}"] .react-flow__edge-text')).to_have_text('子')
        expect(page.locator(f'.family-kinship-label[data-person="{persons[4]["id"]}"] .react-flow__edge-text')).to_have_text('女')
        page.locator(f'.family-kinship-label[data-person="{persons[3]["id"]}"] .react-flow__edge-textwrapper').click()
        expect(page.get_by_role('dialog')).to_contain_text('这组家人的关系')
        expect(page.locator('.family-relation-list>button')).to_have_count(4)
        page.locator('.family-relation-list>button').filter(has_text='叶棠').click()
        expect(page.get_by_role('dialog')).to_contain_text('养父 → 养子')
        expect(page.get_by_role('dialog')).to_contain_text('关系性质：收养')
        page.get_by_role('dialog').get_by_role('button',name='关闭',exact=True).last.click()
        page.get_by_role('button',name='显示设置',exact=True).click()
        page.get_by_label('显示称谓',exact=True).uncheck()
        expect(page.locator('.family-kinship-label')).to_have_count(0)
        page.get_by_label('显示称谓',exact=True).check()
        page.get_by_role('button',name='显示设置',exact=True).click()
        page.screenshot(path=str(OUT/'complex-family-grouped.png'),full_page=True,animations='disabled')
        page.get_by_role('button',name='关系明细',exact=True).click()
        # SVG endpoints must meet the actual card edges, including after rendering scale.
        geometry=page.locator('.react-flow__edge').evaluate_all('''edges=>edges.map(edge=>{
          const path=edge.querySelector('.react-flow__edge-path'),matrix=path.getScreenCTM();
          const start=path.getPointAtLength(0).matrixTransform(matrix),end=path.getPointAtLength(path.getTotalLength()).matrixTransform(matrix);
          return {id:edge.dataset.id,start:{x:start.x,y:start.y},end:{x:end.x,y:end.y}};
        })''')
        boxes={p['id']:page.locator(f'.react-flow__node[data-id="{p["id"]}"]').bounding_box() for p in persons}
        for edge in geometry:
            r=next(r for r in relations if r['id']==edge['id'])
            a,b=boxes[r['data']['from_id']],boxes[r['data']['to_id']]
            if r['data']['type'] in ['parent','adoptive','step']:
                assert abs(edge['start']['y']-(a['y']+a['height']))<3
                assert abs(edge['end']['y']-b['y'])<3
            else:
                if a['x']>b['x']:a,b=b,a
                assert abs(edge['start']['x']-(a['x']+a['width']))<3
                assert abs(edge['start']['y']-(a['y']+a['height']/2))<3
                assert abs(edge['end']['x']-b['x'])<3
                assert abs(edge['end']['y']-(b['y']+b['height']/2))<3
        page.get_by_role('button',name='查关系',exact=True).click()
        page.get_by_label('关系查询起点').select_option(persons[0]['id'])
        page.get_by_label('关系查询终点').select_option(persons[1]['id'])
        expect(page.locator('.relationship-result')).to_contain_text('共同育儿 · 待核实')
        page.get_by_role('dialog',name='我们之间的关系').get_by_role('button',name='关闭',exact=True).last.click()
        page.get_by_role('button',name='家庭树',exact=True).click()
        page.screenshot(path=str(OUT/'complex-family-desktop.png'),full_page=True,animations='disabled')
        # Actual drag persists until explicit layout reset.
        node=page.locator(f'.react-flow__node[data-id="{persons[4]["id"]}"]')
        before=node.bounding_box();x=before['x']+20;y=before['y']+20
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+70,y+35,steps=12);page.mouse.up()
        after=node.bounding_box();assert after['x']>before['x']+50
        page.get_by_role('button',name='一键排版').click()
        expect(page.get_by_role('dialog')).to_have_count(0)
        # Home preview depicts the selected parent's real children only.
        page.get_by_role('button',name='家族首页',exact=True).click()
        assert page.locator('.family-preview [data-parent]').count()==2
        assert page.locator(f'.family-preview [data-child="{persons[1]["id"]}"]').count()==0
        # One family-wide dictionary updates all displays and survives a reload.
        page.get_by_role('button',name='家族设置',exact=True).click()
        page.get_by_role('button',name='称谓设置',exact=True).click()
        page.get_by_label('子的称谓',exact=True).fill('儿子')
        page.get_by_label('女的称谓',exact=True).fill('女儿')
        page.get_by_label('父的称谓',exact=True).fill('父亲')
        page.get_by_label('夫妻关系名称',exact=True).fill('配偶关系')
        page.get_by_label('妻的称谓',exact=True).fill('妻子')
        expect(page.locator('.kinship-live-preview')).to_contain_text('父亲 → 儿子')
        expect(page.locator('.kinship-live-preview')).to_contain_text('配偶关系')
        page.screenshot(path=str(OUT/'kinship-settings-desktop.png'),full_page=True,animations='disabled')
        page.get_by_role('button',name='保存并统一应用',exact=True).click()
        expect(page.get_by_text('称谓已统一更新，本家族所有页面均使用新叫法。')).to_be_visible()
        page.get_by_role('button',name='世系图谱',exact=True).click()
        expect(marriage_edge.locator('.react-flow__edge-text')).to_have_text('妻子')
        expect(page.locator(f'.family-kinship-label[data-person="{persons[3]["id"]}"] .react-flow__edge-text')).to_have_text('儿子')
        expect(page.locator(f'.family-kinship-label[data-person="{persons[4]["id"]}"] .react-flow__edge-text')).to_have_text('女儿')
        page.get_by_role('button',name='查关系',exact=True).click()
        page.get_by_label('关系查询起点').select_option(persons[0]['id'])
        page.get_by_label('关系查询终点').select_option(persons[3]['id'])
        expect(page.locator('.relationship-result')).to_contain_text('儿子')
        page.get_by_role('dialog',name='我们之间的关系').get_by_role('button',name='关闭',exact=True).last.click()
        page.locator(f'.react-flow__node[data-id="{persons[3]["id"]}"] .tree-person').click()
        expect(page.locator('.relative-list>div').filter(has_text='顾言').locator('small')).to_have_text('父亲')
        expect(page.locator('.relative-list>div').filter(has_text='林夏').locator('small')).to_have_text('母')
        expect(page.locator('.relative-list>div').filter(has_text='周宁').locator('small')).to_have_text('继母')
        page.get_by_role('button',name='关闭',exact=True).click()
        page.get_by_role('button',name='家族首页',exact=True).click()
        expect(page.locator('.family-preview text')).to_have_text(['儿子','女儿'])
        page.reload();page.wait_for_load_state('networkidle')
        expect(page.locator('.family-preview text')).to_have_text(['儿子','女儿'])
        page.get_by_role('button',name='家族设置',exact=True).click()
        page.get_by_role('button',name='称谓设置',exact=True).click()
        expect(page.get_by_label('子的称谓',exact=True)).to_have_value('儿子')
        expect(page.get_by_label('夫妻关系名称',exact=True)).to_have_value('配偶关系')
        page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(OUT/'kinship-settings-mobile.png'),full_page=True,animations='disabled')
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        page.get_by_role('button',name='恢复默认简写',exact=True).click()
        page.get_by_role('button',name='保存并统一应用',exact=True).click()
        expect(page.get_by_text('称谓已统一更新，本家族所有页面均使用新叫法。')).to_be_visible()
        page.set_viewport_size({'width':390,'height':844})
        page.get_by_role('button',name='打开导航').click();page.get_by_role('button',name='世系图谱',exact=True).click()
        expect(marriage_edge.locator('.react-flow__edge-text')).to_have_text('妻')
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        page.screenshot(path=str(OUT/'complex-family-mobile.png'),full_page=True,animations='disabled')
        page.get_by_role('button',name='切换深色模式').click()
        page.screenshot(path=str(OUT/'complex-family-dark.png'),full_page=True,animations='disabled')
        assert not errors,errors
        browser.close()
        print(json.dumps({'passed':True,'checks':['family-wide-custom-titles','bulk-edit-preview','all-pages-updated','reload-persistence','restore-defaults','quiet-default-tree','grouped-families','all-original-relations-in-details','optional-labels','legacy-edit','coparent-without-marriage','former-partner','independent-parentage','actual-edge-endpoints','typed-path','drag-and-reset','home-preview','mobile','dark'],'errors':errors},ensure_ascii=False))
finally:
    server.terminate();server.wait(timeout=15);log.close()
