from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, inspect, select
from sqlalchemy.orm import Session

import server.db as db_module
from server.app import app, RATES
from server.db import Base, engine, SessionLocal, User, UserActivity, Member, SiteSetting

PASSWORD = 'site-admin-test-password'


@pytest.fixture
def site(monkeypatch):
    monkeypatch.setenv('QINPU_ALLOW_REGISTRATION', '1')
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    RATES.clear()
    with TestClient(app) as client:
        response = client.post('/api/setup', json={
            'name': '站点所有者', 'email': 'owner@example.test', 'password': PASSWORD, 'demo': False})
        assert response.status_code == 200, response.text
        client.headers['X-CSRF-Token'] = response.json()['csrf']
        yield client


def register(client, email='new@example.test'):
    response = client.post('/api/register', json={
        'name': '林夏', 'email': email, 'password': PASSWORD, 'family_name': '林家的记忆'})
    assert response.status_code == 200, response.text
    client.headers['X-CSRF-Token'] = response.json()['csrf']
    return response.json()


def test_admin_routes_require_site_admin_and_csrf(site):
    with TestClient(app) as guest:
        for path in ('/api/admin/overview', '/api/admin/users'):
            assert guest.get(path).status_code == 401
        assert guest.put('/api/admin/registration', json={'enabled': False, 'version': 0}).status_code == 401
        account = register(guest)
        assert account['families'][0]['role'] == 'owner'
        for path in ('/api/admin/overview', '/api/admin/users'):
            assert guest.get(path).status_code == 403
        assert guest.put('/api/admin/registration', json={'enabled': False, 'version': 0}).status_code == 403
    assert site.put('/api/admin/registration', headers={'X-CSRF-Token': ''}, json={'enabled': False, 'version': 0}).status_code == 403
    assert site.get('/api/status').json()['registration_enabled'] is True


def test_overview_directory_and_family_privacy(site):
    with TestClient(app) as guest:
        account = register(guest)
    own_family = site.get('/api/me').json()['families'][0]['id']
    with SessionLocal() as db:
        db.add(Member(family_id=own_family, user_id=account['user']['id'], role='viewer'))
        db.commit()
    overview = site.get('/api/admin/overview').json()
    assert {key: overview[key] for key in ('users', 'admins', 'families', 'recent_registrations')} == {
        'users': 2, 'admins': 1, 'families': 2, 'recent_registrations': 2}
    data = site.get('/api/admin/users').json()
    assert data['total'] == 2
    user = next(row for row in data['items'] if row['id'] == account['user']['id'])
    assert user['name'] == '林夏' and user['email'] == 'new@example.test'
    assert user['family_count'] == 2
    assert {family['role'] for family in user['families']} == {'viewer', 'owner'}
    assert all(set(family) == {'id', 'name', 'role'} for family in user['families'])
    # Keep the allowlist explicit: never return stored password/recovery/session data.
    assert set(user) == {'id', 'name', 'email', 'admin', 'registered_at', 'last_login_at', 'family_count', 'families'}
    assert user['registered_at'] and user['last_login_at']
    assert site.get('/api/families/' + account['families'][0]['id'] + '/state').status_code == 404


def test_search_pagination_roles_and_legacy_users(site):
    with SessionLocal() as db:
        for index in range(25):
            user = User(email=f'guest{index:02}@example.test', name=f'测试用户{index:02}', password='fixture', recovery='fixture')
            db.add(user)
            db.flush()
            db.add(UserActivity(user_id=user.id, registered_at=(datetime.now(timezone.utc)-timedelta(days=10, minutes=index)).isoformat()))
        db.add(User(email='literal@example.test', name='100%_记录', password='fixture', recovery='fixture'))
        db.commit()
    first = site.get('/api/admin/users').json()
    second = site.get('/api/admin/users?page=2').json()
    assert first['total'] == 27 and len(first['items']) == 20 and len(second['items']) == 7
    assert not ({row['id'] for row in first['items']} & {row['id'] for row in second['items']})
    assert site.get('/api/admin/users?page=999').json()['page'] == 2
    assert site.get('/api/admin/users?role=admin').json()['total'] == 1
    assert site.get('/api/admin/users?role=user').json()['total'] == 26
    assert site.get('/api/admin/users', params={'q': ' GUEST00@EXAMPLE '}).json()['total'] == 1
    assert site.get('/api/admin/users', params={'q': '测试用户'}).json()['total'] == 25
    literal = site.get('/api/admin/users', params={'q': '%_'}).json()
    assert literal['total'] == 1 and literal['items'][0]['registered_at'] is None
    assert literal['items'][0]['last_login_at'] is None and literal['items'][0]['family_count'] == 0
    empty = site.get('/api/admin/users?q=missing&page=20').json()
    assert empty['items'] == [] and empty['page'] == empty['pages'] == 1
    for query in ('page=0', 'page_size=101', 'page_size=0', 'role=owner', 'q='+'a'*101):
        assert site.get('/api/admin/users?'+query).status_code == 422
    assert site.get('/api/admin/overview').json()['recent_registrations'] == 1


def test_legacy_login_and_password_change_timestamps(site):
    me = site.get('/api/me').json()
    uid = me['user']['id']
    with SessionLocal() as db:
        db.execute(delete(UserActivity).where(UserActivity.user_id == uid))
        db.commit()
    response = site.post('/api/login', json={'email': 'owner@example.test', 'password': PASSWORD})
    site.headers['X-CSRF-Token'] = response.json()['csrf']
    row = site.get('/api/admin/users').json()['items'][0]
    assert row['registered_at'] is None and row['last_login_at'] is not None
    response = site.post('/api/account/password', json={'current_password': PASSWORD, 'new_password': PASSWORD+'-changed'})
    assert response.status_code == 200, response.text
    site.headers['X-CSRF-Token'] = response.json()['csrf']
    assert site.get('/api/admin/users').json()['items'][0]['last_login_at'] == row['last_login_at']
    assert site.post('/api/login', json={'email': 'owner@example.test', 'password': PASSWORD+'-changed'}).status_code == 200
    assert site.get('/api/admin/users').json()['items'][0]['last_login_at'] > row['last_login_at']


def test_registration_toggle_persists_and_invitation_still_works(site):
    result = site.put('/api/admin/registration', json={'enabled': False, 'version': 0})
    assert result.status_code == 200, result.text
    assert result.json() == {'enabled': False, 'environment_allowed': True, 'version': 1}
    assert site.get('/api/status').json()['registration_enabled'] is False
    with TestClient(app) as guest:
        assert guest.post('/api/register', json={'name': '林夏', 'email': 'new@example.test', 'password': PASSWORD, 'family_name': '林家'}).status_code == 403
        fid = site.get('/api/me').json()['families'][0]['id']
        code = site.post(f'/api/families/{fid}/invites?role=viewer').json()['code']
        response = guest.post('/api/join', json={'name': '受邀用户', 'email': 'invite@example.test', 'password': PASSWORD, 'code': code})
        assert response.status_code == 200, response.text
        joined = response.json()
    invited = site.get('/api/admin/users?q=invite').json()['items'][0]
    assert invited['registered_at'] and invited['last_login_at'] and invited['families'][0]['role'] == 'viewer'
    assert invited['id'] == joined['user']['id']
    # A fresh application lifespan reads the persisted setting.
    with TestClient(app) as fresh:
        assert fresh.get('/api/status').json()['registration_enabled'] is False
    assert site.put('/api/admin/registration', json={'enabled': True, 'version': 0}).status_code == 409
    assert site.get('/api/status').json()['registration_enabled'] is False
    result = site.put('/api/admin/registration', json={'enabled': True, 'version': 1})
    assert result.status_code == 200 and result.json()['version'] == 2
    with TestClient(app) as guest:
        register(guest)
    with SessionLocal() as db:
        config = db.get(SiteSetting, 'registration').data
        assert config['enabled'] is True and config['updated_by'] and config['updated_at']


def test_environment_remains_registration_upper_bound(site, monkeypatch):
    monkeypatch.setenv('QINPU_ALLOW_REGISTRATION', '0')
    assert site.get('/api/admin/overview').json()['registration'] == {
        'enabled': False, 'environment_allowed': False, 'version': 0}
    assert site.put('/api/admin/registration', json={'enabled': True, 'version': 0}).status_code == 409
    assert site.get('/api/status').json()['registration_enabled'] is False
    monkeypatch.setenv('QINPU_ALLOW_REGISTRATION', '1')
    assert site.get('/api/status').json()['registration_enabled'] is True


def test_admin_without_family_can_use_dashboard_api(site):
    uid = site.get('/api/me').json()['user']['id']
    with SessionLocal() as db:
        db.execute(delete(Member).where(Member.user_id == uid))
        db.commit()
    assert site.get('/api/me').json()['families'] == []
    assert site.get('/api/admin/overview').status_code == 200
    assert site.get('/api/admin/users').json()['items'][0]['families'] == []


def test_additive_schema_upgrade_preserves_legacy_account(tmp_path, monkeypatch):
    legacy_engine = create_engine('sqlite:///'+(tmp_path/'legacy.db').as_posix())
    old_tables = [table for table in Base.metadata.sorted_tables if table.name not in {'user_activity', 'site_settings'}]
    Base.metadata.create_all(legacy_engine, tables=old_tables)
    with Session(legacy_engine) as db:
        db.add(User(id='legacy', email='legacy@example.test', name='历史账号', password='stored-hash', recovery='stored-digest', admin=True))
        db.commit()
    def columns():
        return [{**column, 'type': str(column['type'])} for column in inspect(legacy_engine).get_columns('users')]
    before = columns()
    monkeypatch.setattr(db_module, 'engine', legacy_engine)
    db_module.init_db()
    assert columns() == before
    with Session(legacy_engine) as db:
        user = db.get(User, 'legacy')
        assert user.password == 'stored-hash' and user.recovery == 'stored-digest' and user.admin
        assert db.get(UserActivity, 'legacy') is None
        assert db.scalars(select(SiteSetting)).all() == []
    legacy_engine.dispose()
