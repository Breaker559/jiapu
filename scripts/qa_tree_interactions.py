"""Verify household roles, generation rail, and profile previews in isolated data."""
import io,json,os,subprocess,sys,time,urllib.request
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright,expect

sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'test-results';DATA=OUT/('tree-interactions-'+str(time.time_ns()));DATA.mkdir(parents=True)
env={**os.environ,'QINPU_DATA':str(DATA),'PYTHONUTF8':'1'};env.pop('DATABASE_URL',None)
log=(DATA/'server.log').open('w',encoding='utf-8')
server=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),'-m','uvicorn','server.app:app','--host','127.0.0.1','--port','8878'],cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
BASE='http://127.0.0.1:8878'
try:
    for _ in range(40):
        try:urllib.request.urlopen(BASE+'/api/health',timeout=1);break
        except Exception:time.sleep(.25)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        ctx=browser.new_context(viewport={'width':1440,'height':1100})
        response=ctx.request.post(BASE+'/api/setup',data={'name':'交互测试','email':'tree@example.test','password':'tree-interaction-password','demo':False})
        assert response.ok,response.text()
        auth=response.json();fid=auth['families'][0]['id'];headers={'X-CSRF-Token':auth['csrf']}
        def create(kind,data):
            r=ctx.request.post(f'{BASE}/api/families/{fid}/records/{kind}',data={'data':data},headers=headers)
            assert r.ok,r.text()
            return r.json()
        people=[create('person',{'name':name,'gender':gender,'generation':generation,'bio':f'{name}的生平记录，用于验证悬停资料展示。','birth':{'calendar':'solar','year':year,'month':3,'day':18},'birthplace':'杭州',**({'living':False,'death':{'calendar':'solar','year':2021,'month':10,'day':15}} if name=='顾文' else {})}) for name,gender,generation,year in [('顾文','male','第一代',1946),('顾言','male','第二代',1970),('林夏','female','第二代',1972),('周宁','female','第二代',1973),('顾小满','male','第三代',1998)]]
        def link(a,b,kind):return create('relation',{'from_id':people[a]['id'],'to_id':people[b]['id'],'type':kind})
        former=link(1,2,'former_spouse');link(1,3,'married');link(0,1,'parent');link(1,4,'parent');link(2,4,'parent')
        buffer=io.BytesIO();Image.new('RGB',(180,120),'#7fa69b').save(buffer,format='PNG')
        uploaded=ctx.request.post(f'{BASE}/api/families/{fid}/media',headers=headers,multipart={'metadata':json.dumps({'title':'验收照片','person_ids':[people[1]['id'],people[2]['id']]}),'file':{'name':'preview.png','mimeType':'image/png','buffer':buffer.getvalue()}})
        assert uploaded.ok,uploaded.text()
        page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE+'/#tree');page.wait_for_load_state('networkidle')
        expect(page.get_by_label('当前主角',exact=True)).to_have_count(0)
        expect(page.locator('.tree-main-badge')).to_have_count(0)
        expect(page.locator('.tree-person').filter(has_text='第二代')).to_have_count(0)
        expect(page.locator('.generation-row')).to_have_text(['第一代','第二代','第三代'])
        elder_card=page.locator(f'.react-flow__node[data-id="{people[0]["id"]}"] .tree-person')
        expect(elder_card).to_contain_text('生：1946.03.18');expect(elder_card).to_contain_text('卒：2021.10.15');expect(elder_card).to_contain_text('享年：75岁')
        living_card=page.locator(f'.react-flow__node[data-id="{people[1]["id"]}"] .tree-person')
        expect(living_card).to_contain_text('生日：1970.03.18');expect(living_card).not_to_contain_text('卒：');expect(living_card.locator('.tree-gender')).to_have_text('男')
        expect(living_card.locator('.tree-person-age')).to_contain_text('周岁')
        former_edge=page.locator(f'.react-flow__edge[data-id="{former["id"]}"]')
        expect(former_edge.locator('.react-flow__edge-text')).to_have_text('前妻')
        def marker_side():
            return former_edge.locator('.react-flow__edge-path').evaluate("p=>p.getAttribute('marker-start')?'start':p.getAttribute('marker-end')?'end':'none'")
        before=marker_side();assert before!='none'
        # Child branches keep their titles without repeating parent titles beneath cards.
        expect(page.locator(f'.family-kinship-label[data-person="{people[1]["id"]}"] .react-flow__edge-text')).to_have_text('子')
        expect(page.locator(f'.family-kinship-label[data-person="{people[2]["id"]}"] .react-flow__edge-text')).to_have_count(0)
        page.reload();page.wait_for_load_state('networkidle')
        expect(former_edge.locator('.react-flow__edge-text')).to_have_text('前妻')
        assert marker_side()==before
        page.screenshot(path=str(OUT/'tree-household-desktop.png'),full_page=True,animations='disabled')
        # The pinned generation rail follows zoom/pan in the vertical axis.
        def row_center(label):
            box=page.locator('.generation-row').filter(has_text=label).bounding_box();return box['y']+box['height']/2
        def node_center(index):
            box=page.locator(f'.react-flow__node[data-id="{people[index]["id"]}"]').bounding_box();return box['y']+box['height']/2
        assert abs(row_center('第二代')-node_center(1))<2
        page.get_by_role('button',name='查看全图',exact=True).click();page.wait_for_timeout(350)
        assert abs(row_center('第二代')-node_center(1))<2
        # Hover and move into the popup; tabs stay usable without opening a full modal.
        node=page.locator(f'.react-flow__node[data-id="{people[2]["id"]}"]')
        node.hover()
        popup=page.get_by_role('dialog',name='林夏资料预览')
        expect(popup).to_be_visible();popup.hover();page.wait_for_timeout(300);expect(popup).to_be_visible()
        expect(popup.get_by_role('tabpanel')).to_contain_text('杭州')
        popup.get_by_role('tab',name='生平',exact=True).click()
        expect(popup.get_by_role('tabpanel')).to_contain_text('林夏的生平记录')
        page.screenshot(path=str(OUT/'tree-preview-bio.png'),full_page=False,animations='disabled')
        popup.get_by_role('tab',name='影像',exact=False).click()
        photo=popup.get_by_role('img',name='验收照片',exact=True)
        expect(photo).to_be_visible()
        assert photo.evaluate('i=>i.complete&&i.naturalWidth>0')
        page.screenshot(path=str(OUT/'tree-preview-photos.png'),full_page=False,animations='disabled')
        popup.get_by_role('button',name='亲属关系',exact=True).click()
        expect(popup).not_to_be_visible()
        expect(page.get_by_role('dialog',name='这组家人的关系')).to_be_visible()
        page.get_by_role('dialog').get_by_role('button',name='关闭',exact=True).last.click()
        page.get_by_role('button',name='预览林夏',exact=True).click()
        expect(popup).to_be_visible()
        popup.get_by_role('button',name='完整档案',exact=True).click()
        expect(page.get_by_role('dialog',name='人物档案')).to_be_visible()
        page.keyboard.press('Escape')
        # Touch devices get an explicit info button and a bottom sheet.
        mobile=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,storage_state=ctx.storage_state())
        phone=mobile.new_page();phone.on('pageerror',lambda e:errors.append(str(e)))
        phone.goto(BASE+'/#tree');phone.wait_for_load_state('networkidle')
        phone.get_by_role('button',name='查看全图',exact=True).click();phone.wait_for_timeout(350)
        phone.get_by_role('button',name='预览顾言',exact=True).tap()
        mobile_popup=phone.get_by_role('dialog',name='顾言资料预览');expect(mobile_popup).to_be_visible()
        mobile_popup.get_by_role('tab',name='影像',exact=False).tap()
        expect(mobile_popup.get_by_role('img',name='验收照片')).to_be_visible()
        assert not phone.evaluate('document.documentElement.scrollWidth>innerWidth')
        phone.screenshot(path=str(OUT/'tree-preview-mobile.png'),full_page=False,animations='disabled')
        mobile_popup.get_by_role('button',name='关闭人物预览',exact=True).tap()
        phone.get_by_role('button',name='切换深色模式').tap()
        phone.screenshot(path=str(OUT/'tree-household-dark-mobile.png'),full_page=True,animations='disabled')
        assert not errors,errors
        browser.close()
        print(json.dumps({'passed':True,'checks':['household-direction','arrowheads','stable-on-reload','son-and-father-in-separate-families','generation-rail-zoom','no-card-generation','hover-transfer','biography-tab','photo-tab','family-relations-from-preview','full-profile','touch-preview','dark-mode'],'errors':errors},ensure_ascii=False))
finally:
    server.terminate();server.wait(timeout=15);log.close()
