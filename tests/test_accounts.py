import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from server.app import app, RATES
from server.db import Base, engine, SessionLocal, User, Family

PASSWORD='registration-test-password'

@pytest.fixture
def site(monkeypatch):
    monkeypatch.setenv('QINPU_ALLOW_REGISTRATION','1')
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine);RATES.clear()
    with TestClient(app) as client:
        yield client

def setup(client):
    result=client.post('/api/setup',json={'name':'Owner','email':'owner@example.test','password':PASSWORD,'demo':False})
    assert result.status_code==200,result.text
    client.headers['X-CSRF-Token']=result.json()['csrf']
    return result.json()

def register(client,email='new@example.test',**overrides):
    return client.post('/api/register',json={'name':' 新用户 ','email':email,'password':PASSWORD,'family_name':' 新用户的家族 ',**overrides})

def test_registration_requires_setup_and_valid_names(site):
    assert site.get('/api/status').json()['registration_enabled'] is False
    assert register(site).status_code==409
    setup(site)
    assert site.get('/api/status').json()['registration_enabled'] is True
    assert register(site,name='   ').status_code==422
    assert register(site,family_name='   ').status_code==422
    assert register(site,password='short').status_code==422

def test_public_registration_isolated_owner_without_admin_escalation(site):
    admin=setup(site);fid=admin['families'][0]['id']
    person=site.post(f'/api/families/{fid}/records/person',json={'data':{'name':'原家族私有资料'}}).json()
    with TestClient(app) as newcomer:
        result=register(newcomer,'New@Example.Test',admin=True,role='owner',family_id=fid,demo=True)
        assert result.status_code==200,result.text
        data=result.json();assert data['user']['email']=='new@example.test' and data['user']['name']=='新用户'
        assert data['user']['admin'] is False
        assert len(data['families'])==1 and data['families'][0]['role']=='owner'
        assert data['families'][0]['id']!=fid and data['families'][0]['name']=='新用户的家族'
        newcomer.headers['X-CSRF-Token']=data['csrf'];newfid=data['families'][0]['id']
        assert newcomer.get(f'/api/families/{newfid}/state').json()['records']==[]
        assert newcomer.get(f'/api/families/{fid}/state').status_code==404
        assert newcomer.put(f'/api/families/{fid}/records/{person["id"]}',json={'version':1,'data':{'name':'窜改'}}).status_code==404
        assert newcomer.post(f'/api/families/{newfid}/records/person',json={'data':{'name':'新家族人物'}}).status_code==200
        assert site.get(f'/api/families/{newfid}/state').status_code==404
        assert register(newcomer,' NEW@example.test ').status_code==409
        assert newcomer.get('/api/me').json()['user']['id']==data['user']['id']
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(User))==2
        assert db.scalar(select(func.count()).select_from(Family))==2

def test_registration_switch_preserves_invitation_signup(site,monkeypatch):
    admin=setup(site);fid=admin['families'][0]['id']
    monkeypatch.setenv('QINPU_ALLOW_REGISTRATION','0')
    assert site.get('/api/status').json()['registration_enabled'] is False
    assert register(site).status_code==403
    code=site.post(f'/api/families/{fid}/invites?role=viewer').json()['code']
    with TestClient(app) as guest:
        joined=guest.post('/api/join',json={'name':'受邀用户','email':'invite@example.test','password':PASSWORD,'code':code})
        assert joined.status_code==200,joined.text
        assert joined.json()['user']['admin'] is False
        assert joined.json()['families'][0]['role']=='viewer'

def test_registration_rate_limit(site):
    setup(site)
    for index in range(6):
        with TestClient(app) as guest:
            assert register(guest,f'new{index}@example.test').status_code==200
    assert register(site,'limited@example.test').status_code==429

def test_change_password_keeps_current_session_revokes_others_and_rotates_recovery(site):
    setup(site)
    with TestClient(app) as user, TestClient(app) as other, TestClient(app) as anonymous:
        account=register(user).json();user.headers['X-CSRF-Token']=account['csrf']
        other.post('/api/login',json={'email':'new@example.test','password':PASSWORD})
        data={'current_password':PASSWORD,'new_password':'new-strong-password'}
        assert anonymous.post('/api/account/password',json=data).status_code==401
        assert user.post('/api/account/password',json=data,headers={'X-CSRF-Token':''}).status_code==403
        assert user.post('/api/account/password',json={**data,'current_password':'incorrect'}).status_code==400
        assert other.get('/api/me').status_code==200
        assert user.post('/api/account/password',json={**data,'new_password':PASSWORD}).status_code==422
        assert user.post('/api/account/password',json={**data,'new_password':'short'}).status_code==422
        changed=user.post('/api/account/password',json=data)
        assert changed.status_code==200,changed.text
        fresh=changed.json();assert fresh['csrf']!=account['csrf'] and fresh['recovery']!=account['recovery']
        user.headers['X-CSRF-Token']=fresh['csrf']
        assert user.get('/api/me').status_code==200
        assert other.get('/api/me').status_code==401
        assert site.get('/api/me').status_code==200
        assert anonymous.post('/api/login',json={'email':'new@example.test','password':PASSWORD}).status_code==401
        assert anonymous.post('/api/login',json={'email':'new@example.test','password':data['new_password']}).status_code==200
        assert anonymous.post('/api/recover',json={'email':'new@example.test','recovery':account['recovery'],'password':'another-password'}).status_code==400
        assert anonymous.post('/api/recover',json={'email':'new@example.test','recovery':fresh['recovery'],'password':'another-password'}).status_code==200
        assert user.get('/api/me').status_code==401
