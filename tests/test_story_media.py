import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from server.app import app, open_backup
from scripts.qa_media_fixture import video_bytes
from test_app import client, person, state, upload, guest


def upload_video(c, raw=None, filename='memory.mp4', **metadata):
    result = c.post(f'/api/families/{c.fid}/media',
                    files={'file': (filename, raw if raw is not None else video_bytes(), 'video/mp4')},
                    data={'metadata': json.dumps(metadata)})
    assert result.status_code == 200, result.text
    return result.json()


def story(c, body, **extra):
    return c.post(f'/api/families/{c.fid}/records/story',
                  json={'data': {'title': '旅行记录', 'format': 'markdown', 'body': body, **extra}})


@pytest.mark.parametrize('container_format,codec,mime', [('mp4', 'libx264', 'video/mp4'), ('webm', 'libvpx-vp9', 'video/webm')])
def test_video_playback_range_poster_and_metadata(client, container_format, codec, mime):
    c = client
    raw = video_bytes(container_format, codec)
    item = upload_video(c, raw, filename='memory.' + container_format)
    base = f'/api/families/{c.fid}/media/{item["id"]}'
    assert item['data']['media_type'] == 'video' and item['data']['duration'] == 2
    assert (item['data']['width'], item['data']['height']) == (320, 180)
    display = c.get(base + '/display')
    assert display.headers['content-type'] == mime and display.content == raw
    portion = c.get(base + '/display', headers={'Range': 'bytes=0-99'})
    assert portion.status_code == 206 and portion.content == raw[:100]
    assert portion.headers['content-range'] == f'bytes 0-99/{len(raw)}'
    assert Image.open(io.BytesIO(c.get(base + '/thumb').content)).format == 'JPEG'
    assert c.get(base + '/original').content == raw
    changed = c.put(base, json={**item['data'], 'title': '新的标题'})
    assert changed.status_code == 200, changed.text
    saved = next(row for row in state(c)['records'] if row['id'] == item['id'])
    assert saved['data']['media_type'] == 'video' and saved['data']['title'] == '新的标题'


def test_video_permissions_and_image_only_actions(client):
    c = client
    public = upload_video(c)
    private = upload_video(c, privacy='editors')
    base = f'/api/families/{c.fid}/media/{public["id"]}'
    other = c.post('/api/families', json={'name': '独立家族'}).json()['id']
    with guest(c, 'viewer') as viewer:
        assert viewer.get(base + '/display').status_code == 200
        assert viewer.get(base + '/original').status_code == 403
        assert viewer.get(f'/api/families/{c.fid}/media/{private["id"]}/display').status_code == 404
        assert viewer.get(f'/api/families/{other}/media/{public["id"]}/display').status_code == 404
        assert viewer.post(f'/api/families/{c.fid}/media', files={'file': ('x.mp4', video_bytes())}).status_code == 403
    with TestClient(app) as anonymous:
        assert anonymous.get(base + '/display').status_code == 401
    assert c.get(base + '/avatar').status_code == 422
    assert c.post(base + '/crop', json={'size': 1}).status_code == 422
    assert c.post(f'/api/families/{c.fid}/records/person', json={'data': {'name': '测试', 'avatar': public['id']}}).status_code == 422
    assert c.put(f'/api/families/{c.fid}', json={**state(c)['family'], 'cover': public['id']}).status_code == 422


def test_video_rejects_corruption_and_unplayable_codec(client):
    for raw in [b'not a video', b'\x00\x00\x00\x18ftypisom' + b'broken', video_bytes('mp4', 'mpeg4')]:
        response = client.post(f'/api/families/{client.fid}/media', files={'file': ('broken.mp4', raw, 'video/mp4')})
        assert response.status_code == 422, response.text
    assert state(client)['records'] == []


def test_markdown_references_privacy_plain_compatibility_and_migration(client):
    c = client
    p = person(c, '旅行人物')
    picture = upload(c, title='合影', person_ids=[p['id']])
    video = upload_video(c, title='旅行片段', person_ids=[p['id']])
    private = upload(c, privacy='editors')
    body = f'## 那年的团圆\n\n![合影](media:{picture["id"]})\n\n![旅行](media:{video["id"]})'
    created = story(c, body, media_ids=[private['id']])
    assert created.status_code == 200, created.text
    entry = created.json()
    assert entry['data']['media_ids'] == [picture['id'], video['id']]
    assert story(c, f'![私密](media:{private["id"]})').status_code == 422
    assert story(c, f'![私密](media:{private["id"]})', privacy='editors').status_code == 200
    other = c.post('/api/families', json={'name': '另一个家族'}).json()['id']
    assert c.post(f'/api/families/{other}/records/story', json={'data': entry['data']}).status_code == 422
    plain = story(c, '<b>原始纯文本</b>', format='plain').json()
    assert plain['data']['format'] == 'plain' and plain['data']['media_ids'] == []
    legacy = c.post(f'/api/families/{c.fid}/records/story', json={'data': {'title': '旧档案', 'body': '**原文**'}}).json()
    assert legacy['data']['format'] == 'plain'
    pw = 'markdown-video-backup-password'
    backup = c.post(f'/api/families/{c.fid}/backup', json={'password': pw}).content
    restored = c.post('/api/restore', files={'file': ('media.qinpu', backup)}, data={'password': pw})
    assert restored.status_code == 200, restored.text
    fid = restored.json()['id']
    rows = state(c, fid)['records']
    restored_story = next(r for r in rows if r['kind'] == 'story' and r['data']['body'].startswith('##'))
    restored_video = next(r for r in rows if r['data'].get('media_type') == 'video')
    assert video['id'] not in restored_story['data']['body']
    assert f'media:{restored_video["id"]}' in restored_story['data']['body']
    assert restored_video['id'] in restored_story['data']['media_ids']
    base = f'/api/families/{fid}/media/{restored_video["id"]}'
    assert c.get(base + '/display').content == c.get(f'/api/families/{c.fid}/media/{video["id"]}/display').content
    assert Image.open(io.BytesIO(c.get(base + '/thumb').content)).size == (320, 180)
    migrated_backup = c.post(f'/api/families/{fid}/backup', json={'password': pw}).content
    archive, manifest = open_backup(migrated_backup, pw)
    archive.close()
    historical = next(log['after'] for log in manifest['history'] if isinstance(log.get('after'), dict) and log['after'].get('body', '').startswith('##'))
    assert restored_video['id'] in historical['body'] and video['id'] not in historical['body']


def test_birthday_primary_calendar_and_secondary_conversion(client):
    c = client
    person(c, '农历生日', birth={'calendar': 'lunar', 'year': 2024, 'month': 1, 'day': 1})
    person(c, '阳历生日', birth={'calendar': 'solar', 'year': 2024, 'month': 2, 'day': 10})
    person(c, '年份不详', birth={'calendar': 'lunar', 'month': 8, 'day': 15})
    person(c, '仅年份', birth={'calendar': 'solar', 'year': 2000})
    people = {r['data']['name']: r for r in state(c)['records']}
    lunar = people['农历生日']['anniversary']
    assert lunar['primary_label'] == '农历 正月初一' and lunar['secondary_label'].startswith('阳历 ')
    assert lunar['display_month'] == '正月' and lunar['display_day'] == '初一'
    solar = people['阳历生日']['anniversary']
    assert solar['primary_label'].startswith('阳历 ') and solar['secondary_label'].startswith('农历 ')
    assert solar['display_month'] == '2月' and solar['display_day'] == '10'
    assert people['年份不详']['birth_info']['solar'] is None
    assert people['仅年份']['anniversary'] is None
