import io,json,zipfile,hashlib
from datetime import date
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from server.app import app, RATES, open_backup, derive
from server.db import Base,engine
from server.dates import FamilyDate,date_info,next_anniversary
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

@pytest.fixture
def client():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine);RATES.clear()
    with TestClient(app) as c:
        result=c.post('/api/setup',json={'email':'owner@example.test','password':'test-password-123','name':'测试所有者','demo':False})
        assert result.status_code==200,result.text
        c.headers['X-CSRF-Token']=result.json()['csrf'];c.fid=result.json()['families'][0]['id'];c.recovery=result.json()['recovery']
        yield c

def person(c,name='测试人物',**extra):
    r=c.post(f'/api/families/{c.fid}/records/person',json={'data':{'name':name,**extra}})
    assert r.status_code==200,r.text
    return r.json()
def state(c,fid=None):return c.get(f'/api/families/{fid or c.fid}/state').json()
def image_bytes():
    b=io.BytesIO();Image.new('RGB',(240,160),'#87ae9a').save(b,format='PNG');return b.getvalue()
def upload(c,**metadata):
    r=c.post(f'/api/families/{c.fid}/media',files={'file':('test.png',image_bytes(),'image/png')},data={'metadata':json.dumps(metadata)})
    assert r.status_code==200,r.text
    return r.json()
def guest(c,role):
    inv=c.post(f'/api/families/{c.fid}/invites?role={role}').json()['code']
    g=TestClient(app);result=g.post('/api/join',json={'name':role,'email':role+'@example.test','password':'test-password-456','code':inv})
    assert result.status_code==200,result.text
    g.headers['X-CSRF-Token']=result.json()['csrf'];g.fid=c.fid;return g

def test_auth_csrf_origin_and_setup_guard(client):
    c=client
    assert c.post('/api/setup',json={'email':'x@y.test','password':'test-password'}).status_code==409
    assert TestClient(app).get(f'/api/families/{c.fid}/state').status_code==401
    assert c.post('/api/families',json={'name':'x'},headers={'X-CSRF-Token':''}).status_code==403
    assert c.post('/api/families',json={'name':'x'},headers={'Origin':'https://evil.example'}).status_code==403
    assert c.get('/api/me').headers['cache-control']=='no-store'

def test_family_and_media_isolation(client):
    c=client;p=person(c);m=upload(c,person_ids=[p['id']]);other=c.post('/api/families',json={'name':'另一个家族'}).json()['id']
    assert not state(c,other)['records']
    assert c.get(f'/api/families/{other}/media/{m["id"]}/display').status_code==404
    assert c.put(f'/api/families/{other}/records/{p["id"]}',json={'data':{'name':'窃改'},'version':1}).status_code==404
    r=c.post(f'/api/families/{other}/records/relation',json={'data':{'from_id':p['id'],'to_id':'absent','type':'parent'}})
    assert r.status_code==404

def test_viewer_private_records_and_write_restrictions(client):
    c=client;private=person(c,'私密',privacy='editors');public=person(c,'可见');photo=upload(c,person_ids=[private['id']])
    c.post(f'/api/families/{c.fid}/records/relation',json={'data':{'from_id':private['id'],'to_id':public['id'],'type':'parent'}})
    g=guest(c,'viewer');visible=state(g)['records']
    assert [r['id'] for r in visible]==[public['id']]
    assert g.get(f'/api/families/{c.fid}/media/{photo["id"]}/thumb').status_code==404
    assert g.post(f'/api/families/{c.fid}/records/person',json={'data':{'name':'无权限'}}).status_code==403
    assert g.get(f'/api/families/{c.fid}/export.csv').status_code==403
    assert g.post(f'/api/families/{c.fid}/backup',json={'password':'backup-password'}).status_code==403
    g.close()

def test_relationship_cycles_duplicates_and_version_conflict(client):
    c=client;a,b,d=person(c,'祖'),person(c,'父'),person(c,'子')
    def link(x,y,t='parent'):return c.post(f'/api/families/{c.fid}/records/relation',json={'data':{'from_id':x['id'],'to_id':y['id'],'type':t}})
    assert link(a,b).status_code==200
    assert link(b,d,'adoptive').status_code==200
    assert link(d,a).status_code==422
    assert link(a,b).status_code==409
    assert link(a,a).status_code==422
    assert c.put(f'/api/families/{c.fid}/records/{a["id"]}',json={'data':{'name':'更新'},'version':1}).status_code==200
    assert c.put(f'/api/families/{c.fid}/records/{a["id"]}',json={'data':{'name':'旧版本覆盖'},'version':1}).status_code==409
    assert c.delete(f'/api/families/{c.fid}/records/{a["id"]}?version=2').status_code==409

def test_calendar_conversion_and_boundaries():
    lunar=date_info({'calendar':'lunar','year':2024,'month':1,'day':1})
    assert lunar['solar']=='2024-02-10'
    assert date_info({'calendar':'solar','year':2024,'month':2,'day':10})['lunar']=='2024年正月初一'
    assert date_info({'calendar':'lunar','year':2023,'month':2,'day':1,'leap':True})['solar']=='2023-03-22'
    with pytest.raises(ValueError):FamilyDate(calendar='lunar',year=2024,month=2,day=1,leap=True)
    with pytest.raises(ValueError):FamilyDate(calendar='solar',year=2023,month=2,day=29)
    assert date_info({'calendar':'solar','year':1800,'month':1,'day':1})['lunar'] is None
    assert date_info({'calendar':'lunar','month':8,'day':15})['solar'] is None
    assert next_anniversary({'calendar':'solar','year':2000,'month':2,'day':29},today=date(2025,1,1))['date']=='2025-02-28'
    assert next_anniversary({'calendar':'solar','year':2000,'month':2,'day':29},missing='next',today=date(2025,1,1))['date']=='2025-03-01'
    assert next_anniversary({'calendar':'lunar','month':1,'day':1},today=date(2024,1,1))['date']=='2024-02-10'

def test_complex_family_relations_and_editing(client):
    c=client
    a,b,d,child=[person(c,n) for n in ['家长甲','家长乙','家长丙','孩子']]
    def link(x,y,t,**data):
        return c.post(f'/api/families/{c.fid}/records/relation',json={'data':{'from_id':x['id'],'to_id':y['id'],'type':t,**data}})
    legacy=link(a,b,'spouse').json()
    changed=c.put(f'/api/families/{c.fid}/records/{legacy["id"]}',json={'version':1,'data':{**legacy['data'],'type':'coparent','certainty':'uncertain','note':'一起照顾孩子，关系待核实'}})
    assert changed.status_code==200,changed.text
    updated=next(r for r in state(c)['records'] if r['id']==legacy['id'])
    assert updated['version']==2 and updated['data']['type']=='coparent'
    assert len([r for r in state(c)['records'] if r['kind']=='relation'])==1
    assert link(a,child,'parent').status_code==200
    assert link(b,child,'adoptive').status_code==200
    assert link(d,child,'step').status_code==200
    assert link(a,d,'married').status_code==200
    assert link(b,d,'former_spouse').status_code==200
    assert link(child,a,'parent_unknown').status_code==422
    stale=c.put(f'/api/families/{c.fid}/records/{legacy["id"]}',json={'version':1,'data':legacy['data']})
    assert stale.status_code==409
    # A viewer cannot edit any kind of relationship.
    g=guest(c,'viewer')
    assert g.put(f'/api/families/{c.fid}/records/{legacy["id"]}',json={'version':2,'data':legacy['data']}).status_code==403
    g.close()

def test_symmetric_relations_reverse_duplicates_and_backup(client):
    c=client;a,b=person(c,'甲'),person(c,'乙')
    kinds=['married','partner','former_spouse','former_partner','coparent','other','spouse']
    for kind in kinds:
        data={'from_id':a['id'],'to_id':b['id'],'type':kind,'certainty':'uncertain','note':'关系历史与口述记录'}
        r=c.post(f'/api/families/{c.fid}/records/relation',json={'data':data})
        assert r.status_code==200,r.text
        reverse={**data,'from_id':b['id'],'to_id':a['id']}
        assert c.post(f'/api/families/{c.fid}/records/relation',json={'data':reverse}).status_code==409
    pw='complex-backup-password'
    blob=c.post(f'/api/families/{c.fid}/backup',json={'password':pw}).content
    restored=c.post('/api/restore',files={'file':('complex.qinpu',blob)},data={'password':pw})
    assert restored.status_code==200,restored.text
    rows=state(c,restored.json()['id'])['records'];rels=[r for r in rows if r['kind']=='relation']
    assert sorted(r['data']['type'] for r in rels)==sorted(kinds)
    assert all(r['data']['certainty']=='uncertain' and r['data']['note']=='关系历史与口述记录' for r in rels)
    assert all(r['data']['from_id'] not in [a['id'],b['id']] for r in rels)

def test_images_preserve_original_and_reject_invalid(client):
    c=client;m=upload(c)
    raw=c.get(f'/api/families/{c.fid}/media/{m["id"]}/original')
    assert raw.content==image_bytes()
    assert c.post(f'/api/families/{c.fid}/media/{m["id"]}/crop',json={'size':.6,'rotation':90}).status_code==200
    cropped=c.get(f'/api/families/{c.fid}/media/{m["id"]}/avatar')
    assert Image.open(io.BytesIO(cropped.content)).size==(400,400)
    assert c.get(f'/api/families/{c.fid}/media/{m["id"]}/original').content==image_bytes()
    assert c.post(f'/api/families/{c.fid}/media',files={'file':('fake.jpg',b'<script>alert(1)</script>','image/jpeg')}).status_code==422

def test_shared_photo_keeps_separate_person_crops(client):
    c=client;a=person(c,'左侧人物');b=person(c,'右侧人物')
    buf=io.BytesIO();im=Image.new('RGB',(400,200),'red');im.paste(Image.new('RGB',(200,200),'blue'),(200,0));im.save(buf,format='PNG')
    r=c.post(f'/api/families/{c.fid}/media',files={'file':('two.png',buf.getvalue(),'image/png')});mid=r.json()['id']
    assert c.post(f'/api/families/{c.fid}/media/{mid}/crop',json={'person_id':a['id'],'x':0,'size':1}).status_code==200
    assert c.post(f'/api/families/{c.fid}/media/{mid}/crop',json={'person_id':b['id'],'x':1,'size':1}).status_code==200
    left=c.get(f'/api/families/{c.fid}/media/{mid}/avatar?person={a["id"]}').content
    right=c.get(f'/api/families/{c.fid}/media/{mid}/avatar?person={b["id"]}').content
    assert left!=right
    assert Image.open(io.BytesIO(left)).getpixel((200,200))[0]>240
    assert Image.open(io.BytesIO(right)).getpixel((200,200))[2]>240

def test_encrypted_backup_preview_restore_and_checksum(client):
    c=client;p=person(c,'照片人物',birth={'calendar':'lunar','year':2024,'month':1,'day':1});m=upload(c,person_ids=[p['id']]);pw='strong-backup-password'
    c.put(f'/api/families/{c.fid}/records/{p["id"]}',json={'version':1,'data':{**p['data'],'avatar':m['id']}})
    result=c.post(f'/api/families/{c.fid}/backup',json={'password':pw});assert result.status_code==200,result.text
    blob=result.content;assert blob.startswith(b'QINPU1') and b'users' not in blob
    assert c.post('/api/restore-preview',files={'file':('backup.qinpu',blob)},data={'password':'wrong'}).status_code==422
    preview=c.post('/api/restore-preview',files={'file':('backup.qinpu',blob)},data={'password':pw});assert preview.json()['counts']['media']==1
    restored=c.post('/api/restore',files={'file':('backup.qinpu',blob)},data={'password':pw});assert restored.status_code==200,restored.text
    fid=restored.json()['id'];assert fid!=c.fid
    rows=state(c,fid)['records'];person2=next(r for r in rows if r['kind']=='person');media2=next(r for r in rows if r['kind']=='media')
    assert person2['id']!=p['id'] and person2['data']['avatar']==media2['id']
    assert media2['data']['person_ids']==[person2['id']]
    assert c.get(f'/api/families/{fid}/media/{media2["id"]}/original').content==image_bytes()
    tampered=bytearray(blob);tampered[-1]^=1
    assert c.post('/api/restore-preview',files={'file':('x.qinpu',bytes(tampered))},data={'password':pw}).status_code==422

def test_recovery_revokes_sessions_and_rotates_code(client):
    c=client;anon=TestClient(app)
    r=anon.post('/api/recover',json={'email':'owner@example.test','recovery':c.recovery,'password':'changed-password-123'})
    assert r.status_code==200 and r.json()['recovery']!=c.recovery
    assert c.get('/api/me').status_code==401
    assert anon.post('/api/recover',json={'email':'owner@example.test','recovery':c.recovery,'password':'changed-password-123'}).status_code==400

def test_proposal_review_and_recycle_history(client):
    c=client;p=person(c,'原名');g=guest(c,'contributor')
    proposed=g.post(f'/api/families/{c.fid}/proposals',json={'kind':'person','target':p['id'],'data':{'name':'修订姓名'},'reason':'采访核对','version':1})
    assert proposed.status_code==200,proposed.text
    assert state(c)['records'][0]['data']['name']=='原名'
    assert c.post(f'/api/families/{c.fid}/proposals/{proposed.json()["id"]}/review?approve=true').status_code==200
    assert next(r for r in state(c)['records'] if r['id']==p['id'])['data']['name']=='修订姓名'
    a=next(a for a in state(c)['audit'] if a['action']=='采纳修改建议')
    assert c.post(f'/api/families/{c.fid}/history/{a["id"]}/restore',json={'data':{},'version':2}).status_code==200
    assert next(r for r in state(c)['records'] if r['id']==p['id'])['data']['name']=='原名'
    assert c.delete(f'/api/families/{c.fid}/records/{p["id"]}?version=3').status_code==200
    assert c.get(f'/api/families/{c.fid}/trash').json()[0]['id']==p['id']
    assert c.post(f'/api/families/{c.fid}/restore/{p["id"]}').status_code==200

def test_csv_preview_duplicate_and_formula_escape(client):
    c=client;person(c,'=HYPERLINK("bad")',birth={'year':2000,'month':1,'day':1})
    content=c.get(f'/api/families/{c.fid}/export.csv').content
    assert b"'=HYPERLINK" in content
    rows='姓名,性别,出生年,出生月,出生日\n新人物,female,2000,1,1\n'.encode('utf-8')
    r=c.post(f'/api/families/{c.fid}/import-csv',files={'file':('test.csv',rows)})
    assert r.json()['count']==1 and len(state(c)['records'])==1
    assert c.post(f'/api/families/{c.fid}/import-csv',files={'file':('test.csv',rows)},data={'commit':'true'}).json()['count']==1
    assert c.post(f'/api/families/{c.fid}/import-csv',files={'file':('test.csv',rows)},data={'commit':'true'}).json()['count']==0

def test_kinship_bulk_settings_permissions_isolation_validation_and_conflict(client):
    c=client;a=person(c,'父',gender='male');b=person(c,'子',gender='male')
    c.post(f'/api/families/{c.fid}/records/relation',json={'data':{'from_id':a['id'],'to_id':b['id'],'type':'parent'}})
    before=state(c);other=c.post('/api/families',json={'name':'独立家族'}).json()['id']
    endpoint=f'/api/families/{c.fid}/kinship'
    assert c.put(endpoint,json={'terms':{'son':'儿子','father':'父亲'},'version':0}).status_code==200
    updated=state(c)
    assert updated['family']['kinship_terms']=={'son':'儿子','father':'父亲'}
    assert updated['records']==before['records']
    assert state(c,other)['family']['kinship_terms']=={}
    for role in ['viewer','editor']:
        g=guest(c,role)
        assert state(g)['family']['kinship_terms']['son']=='儿子'
        assert g.put(endpoint,json={'terms':{'son':'改称'},'version':1}).status_code==403
        g.close()
    assert c.put(endpoint,json={'terms':{'son':'旧版覆盖'},'version':0}).status_code==409
    for terms in [{'son':' '},{'son':'字'*13},{'son':'儿\n子'},{'unknown_key':'伪造'},{'son':42}]:
        assert c.put(endpoint,json={'terms':terms,'version':1}).status_code==422
    # Saving unrelated settings from an older form must not erase custom names.
    assert c.put(f'/api/families/{c.fid}',json={**before['family'],'name':'重新命名'}).status_code==200
    assert state(c)['family']['kinship_terms']=={'son':'儿子','father':'父亲'}
    assert c.put(endpoint,json={'terms':{},'version':1}).status_code==200
    final=state(c)
    assert final['family']['kinship_terms']=={} and final['family']['kinship_version']==2
    assert len([a for a in final['audit'] if a['action']=='批量更新家族称谓'])==2

def test_custom_kinship_survives_encrypted_family_migration(client):
    c=client;terms={'son':'儿子','daughter':'女儿','adoptive_son':'养子','marriage':'配偶关系','past_marriage':'过往婚姻'}
    assert c.put(f'/api/families/{c.fid}/kinship',json={'terms':terms,'version':0}).status_code==200
    pw='terms-backup-password'
    blob=c.post(f'/api/families/{c.fid}/backup',json={'password':pw}).content
    restored=c.post('/api/restore',files={'file':('terms.qinpu',blob)},data={'password':pw})
    assert restored.status_code==200,restored.text
    family=state(c,restored.json()['id'])['family']
    assert family['kinship_terms']==terms and family['kinship_version']==1
