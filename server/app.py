from __future__ import annotations
import csv, hashlib, io, json, os, re, secrets, shutil, threading, time, zipfile
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta, timezone
from typing import Literal
from pathlib import Path
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Request, Response, HTTPException, UploadFile, File, Form, Depends, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select, update, delete, func, or_
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError, BaseModel, Field
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from PIL import Image, ImageOps, UnidentifiedImageError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from .db import *
from .schemas import *
from .dates import date_info, next_anniversary, LunarDate, MONTHS, DAYS
from .seed import FAMILY, example, seed_family
from .videos import IMAGE_LIMIT, VIDEO_LIMIT, FAMILY_MEDIA_LIMIT, looks_like_video, make_video

Image.MAX_IMAGE_PIXELS=30_000_000
hasher=PasswordHasher()
COOKIE='qinpu_session'
LOCK=threading.RLock()
RATES=defaultdict(list)
EDITORS={'owner','editor'}
KINDS={'person','relation','story'}
PARENTS={'parent','adoptive','step','parent_unknown'}
SYMMETRIC_RELATIONS={'married','partner','former_spouse','former_partner','coparent','other','spouse'}
SECURE=os.environ.get('QINPU_SECURE_COOKIE','0')=='1'
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def fail(code,message):raise HTTPException(code,message)
def today_cn():return datetime.now(ZoneInfo('Asia/Shanghai')).date()

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app=FastAPI(title='家谱 API',version='0.1.0',lifespan=lifespan,docs_url=None,redoc_url=None)
# Loopback stays valid for the container health probe when only a public domain is configured.
ALLOWED_HOSTS=list(dict.fromkeys(['127.0.0.1','localhost',*[host.strip() for host in os.environ.get('QINPU_ALLOWED_HOSTS','testserver').split(',') if host.strip()]]))
app.add_middleware(TrustedHostMiddleware,allowed_hosts=ALLOWED_HOSTS)

@app.middleware('http')
async def protection(request,call_next):
    if request.url.path.startswith('/api/') and request.method in {'POST','PUT','PATCH','DELETE'}:
        origin=request.headers.get('origin')
        allowed={str(request.base_url).rstrip('/'), *[value.strip().rstrip('/') for value in os.environ.get('QINPU_ORIGINS','http://127.0.0.1:5173,http://localhost:5173').split(',') if value.strip()]}
        if origin and origin not in allowed:return JSONResponse({'detail':'请求来源不被允许'},403)
        if int(request.headers.get('content-length','0'))>260*1024*1024:return JSONResponse({'detail':'上传内容超过限制'},413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; font-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path.startswith('/api/'):response.headers['Cache-Control']='no-store'
    if SECURE:response.headers['Strict-Transport-Security']='max-age=31536000'
    return response

@app.exception_handler(ValidationError)
async def validation_error(request,exc):return JSONResponse({'detail':'资料格式有误：'+str(exc.errors()[0].get('msg','请检查输入'))},422)

def db_session():
    with SessionLocal() as db:yield db

def rate(request,kind,limit=12):
    key=((request.client.host if request.client else 'local'),kind)
    t=time.time()
    with LOCK:
        if len(RATES)>10000:RATES.clear()
        RATES[key]=[x for x in RATES[key] if t-x<300]
        if len(RATES[key])>=limit:fail(429,'操作过于频繁，请五分钟后再试')
        RATES[key].append(t)

def current(request:Request,db=Depends(db_session)):
    raw=request.cookies.get(COOKIE,'')
    session=db.get(LoginSession,digest(raw)) if raw else None
    if not session or session.expires<int(time.time()):fail(401,'请先登录')
    if request.method not in {'GET','HEAD','OPTIONS'} and not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),session.csrf):fail(403,'会话校验失败，请刷新后重试')
    user=db.get(User,session.user_id)
    if not user:fail(401,'账号不存在')
    return user

def site_admin(user=Depends(current)):
    if not user.admin:fail(403,'仅站点管理员可以访问管理后台')
    return user

def access(db,fid,user,roles=None):
    member=db.scalar(select(Member).where(Member.family_id==fid,Member.user_id==user.id))
    if not member:fail(404,'家族不存在或无权访问')
    if roles and member.role not in roles:fail(403,'当前角色没有此操作权限')
    return member.role

def rec(db,fid,rid,kind=None,deleted=False):
    conditions=[Record.id==rid,Record.family_id==fid,Record.deleted==deleted]
    if kind:conditions.append(Record.kind==kind)
    result=db.scalar(select(Record).where(*conditions))
    if not result:fail(404,'资料不存在或已移入回收站')
    return result

def records(db,fid,deleted=False):return list(db.scalars(select(Record).where(Record.family_id==fid,Record.deleted==deleted)))
def audit(db,fid,user,action,target='',before=None,after=None):
    db.add(Audit(family_id=fid,actor=user.name,action=action,target=target,before=before,after=after))
def pack(r):return {'id':r.id,'kind':r.kind,'data':r.data,'version':r.version,'created':r.created,'updated':r.updated,'deleted':r.deleted}

def visible_records(rows,role):
    if role in EDITORS:return rows
    people={r.id for r in rows if r.kind=='person' and r.data.get('privacy')!='editors'}
    return [r for r in rows if r.data.get('privacy')!='editors' and r.kind!='proposal' and (r.kind!='relation' or {r.data['from_id'],r.data['to_id']}<=people) and (r.kind not in {'media','story'} or set(r.data.get('person_ids',[]))<=people)]

def enrich(items):
    for item in items:
        if item['kind']=='person':
            item['birth_info']=date_info(item['data'].get('birth'))
            item['death_info']=date_info(item['data'].get('death'))
            if item['data'].get('living',True):
                d=item['data'];item['anniversary']=next_anniversary(d.get('birth',{}),d.get('anniversary_calendar','original'),d.get('leap_policy','regular'),d.get('missing_policy','last'),today_cn())
                anniversary=item['anniversary']
                if anniversary:
                    target=date.fromisoformat(anniversary['date'])
                    lunar=LunarDate.fromSolarDate(target.year,target.month,target.day)
                    lunar_month=('闰' if lunar.isLeapMonth else '')+MONTHS[lunar.month-1]+'月'
                    lunar_day=DAYS[lunar.day-1]
                    lunar_label=f'农历 {lunar_month}{lunar_day}'
                    is_lunar=anniversary['calendar']=='lunar'
                    anniversary.update({'display_month':lunar_month if is_lunar else f'{target.month}月','display_day':lunar_day if is_lunar else str(target.day),
                                        'primary_label':lunar_label if is_lunar else f'阳历 {target.isoformat()}',
                                        'secondary_label':f'阳历 {target.isoformat()}' if is_lunar else lunar_label})
    return items

def family_list(db,user):
    return [{'id':f.id,**f.data,'role':m.role} for f,m in db.execute(select(Family,Member).join(Member,Member.family_id==Family.id).where(Member.user_id==user.id)).all()]

def establish(db,user,response,track_login=True):
    raw=secrets.token_urlsafe(48);csrf=secrets.token_urlsafe(32)
    if track_login:
        activity=db.get(UserActivity,user.id)
        if activity is None:
            activity=UserActivity(user_id=user.id);db.add(activity)
        activity.last_login_at=now()
    db.add(LoginSession(id=digest(raw),user_id=user.id,csrf=csrf,expires=int(time.time())+7*86400))
    db.execute(delete(LoginSession).where(LoginSession.expires<int(time.time())))
    db.commit()
    response.set_cookie(COOKIE,raw,httponly=True,secure=SECURE,samesite='strict',max_age=7*86400,path='/')
    return {'user':{'id':user.id,'name':user.name,'email':user.email,'admin':user.admin},'csrf':csrf,'families':family_list(db,user)}

def registration_configuration(db):
    environment_allowed=os.environ.get('QINPU_ALLOW_REGISTRATION','1').strip()=='1'
    setting=db.get(SiteSetting,'registration')
    data=setting.data if setting else {}
    return {'enabled':environment_allowed and data.get('enabled',True),'environment_allowed':environment_allowed,'version':data.get('version',0)}

def registration_allowed(db):return registration_configuration(db)['enabled']

@app.get('/api/status')
def status(db=Depends(db_session)):
    initialized=db.get(Setup,1) is not None
    return {'initialized':initialized,'registration_enabled':initialized and registration_allowed(db),'version':'0.1.0'}

@app.get('/api/demo')
def demo():return {'family':{'id':'demo',**FAMILY,'role':'viewer'},'records':enrich(example()),'audit':[],'members':[]}

@app.post('/api/setup')
def setup(body:Credentials,request:Request,response:Response,db=Depends(db_session)):
    rate(request,'setup',6)
    with LOCK:
        if db.get(Setup,1):fail(409,'管理员已创建，请登录')
        recovery=secrets.token_urlsafe(24)
        user=User(email=body.email,name=body.name,password=hasher.hash(body.password),recovery=digest(recovery),admin=True)
        try:
            db.add(Setup(id=1));db.add(user);db.flush()
            db.add(UserActivity(user_id=user.id,registered_at=now()))
            f=Family(data=FAMILY.copy() if body.demo else FamilyInput(name='我的家族').model_dump())
            db.add(f);db.flush();db.add(Member(family_id=f.id,user_id=user.id,role='owner'))
            if body.demo:seed_family(db,f.id)
            db.commit()
        except IntegrityError:
            db.rollback();fail(409,'初始化已经完成，请登录')
        return {**establish(db,user,response),'recovery':recovery}

@app.post('/api/register')
def register(body:Registration,request:Request,response:Response,db=Depends(db_session)):
    rate(request,'register',6)
    with LOCK:
        if not db.get(Setup,1):fail(409,'请先由站点所有者创建管理员')
        if not registration_allowed(db):fail(403,'本站暂未开放注册，请使用家族邀请码加入')
        if db.scalar(select(User.id).where(User.email==body.email)):fail(409,'该邮箱已注册，请直接登录或恢复密码')
        recovery=secrets.token_urlsafe(24)
        user=User(email=body.email,name=body.name,password=hasher.hash(body.password),recovery=digest(recovery),admin=False)
        try:
            db.add(user);db.flush()
            db.add(UserActivity(user_id=user.id,registered_at=now()))
            family=Family(data=FamilyInput(name=body.family_name).model_dump())
            db.add(family);db.flush()
            db.add(Member(family_id=family.id,user_id=user.id,role='owner'))
            audit(db,family.id,user,'注册账号并创建家族')
            db.commit()
        except IntegrityError:
            db.rollback();fail(409,'该邮箱已注册，请直接登录或恢复密码')
        return {**establish(db,user,response),'recovery':recovery}

@app.post('/api/login')
def login(body:Credentials,request:Request,response:Response,db=Depends(db_session)):
    rate(request,'login')
    user=db.scalar(select(User).where(User.email==body.email))
    try:
        if not user:
            hasher.hash(body.password);fail(401,'邮箱或密码不正确')
        hasher.verify(user.password,body.password)
    except (VerifyMismatchError,InvalidHashError):fail(401,'邮箱或密码不正确')
    return establish(db,user,response)

class Recovery(BaseModel):
    email:str=Field(max_length=200)
    recovery:str=Field(max_length=100)
    password:str=Field(min_length=10,max_length=128)

@app.post('/api/recover')
def recover(body:Recovery,request:Request,db=Depends(db_session)):
    rate(request,'recovery',6)
    with LOCK:
        user=db.scalar(select(User).where(User.email==body.email.lower().strip()))
        if not user or not secrets.compare_digest(user.recovery,digest(body.recovery)):fail(400,'邮箱或恢复码不正确')
        new=secrets.token_urlsafe(24);user.recovery=digest(new);user.password=hasher.hash(body.password)
        db.execute(delete(LoginSession).where(LoginSession.user_id==user.id));db.commit()
    return {'recovery':new}

@app.get('/api/me')
def me(request:Request,user=Depends(current),db=Depends(db_session)):
    session=db.get(LoginSession,digest(request.cookies[COOKIE]))
    return {'user':{'id':user.id,'name':user.name,'email':user.email,'admin':user.admin},'csrf':session.csrf,'families':family_list(db,user)}

@app.post('/api/logout')
def logout(request:Request,response:Response,user=Depends(current),db=Depends(db_session)):
    db.execute(delete(LoginSession).where(LoginSession.id==digest(request.cookies[COOKIE])));db.commit();response.delete_cookie(COOKIE);return {'ok':True}

@app.post('/api/account/password')
def change_password(body:PasswordChange,request:Request,response:Response,user=Depends(current),db=Depends(db_session)):
    rate(request,'change-password',6)
    with LOCK:
        db.refresh(user)
        try:hasher.verify(user.password,body.current_password)
        except (VerifyMismatchError,InvalidHashError):fail(400,'当前密码不正确')
        if body.current_password==body.new_password:fail(422,'新密码不能与当前密码相同')
        recovery=secrets.token_urlsafe(24)
        user.password=hasher.hash(body.new_password);user.recovery=digest(recovery)
        db.execute(delete(LoginSession).where(LoginSession.user_id==user.id))
        for membership in db.scalars(select(Member).where(Member.user_id==user.id)):
            audit(db,membership.family_id,user,'修改本人登录密码',user.id)
        # establish commits the password change and replacement session together.
        return {**establish(db,user,response,track_login=False),'recovery':recovery}

@app.get('/api/admin/overview')
def admin_overview(user=Depends(site_admin),db=Depends(db_session)):
    cutoff=(datetime.now(timezone.utc)-timedelta(days=7)).isoformat()
    return {
        'users':db.scalar(select(func.count()).select_from(User)),
        'admins':db.scalar(select(func.count()).select_from(User).where(User.admin.is_(True))),
        'families':db.scalar(select(func.count()).select_from(Family)),
        'recent_registrations':db.scalar(select(func.count()).select_from(UserActivity).where(UserActivity.registered_at>=cutoff)),
        'registration':registration_configuration(db),
    }

@app.get('/api/admin/users')
def admin_users(q:str=Query('',max_length=100),role:Literal['all','admin','user']='all',page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),user=Depends(site_admin),db=Depends(db_session)):
    conditions=[]
    term=q.strip().lower()
    if term:conditions.append(or_(func.lower(User.name).contains(term,autoescape=True),func.lower(User.email).contains(term,autoescape=True)))
    if role!='all':conditions.append(User.admin.is_(role=='admin'))
    total=db.scalar(select(func.count()).select_from(User).where(*conditions))
    pages=max(1,(total+page_size-1)//page_size);page=min(page,pages)
    rows=db.execute(select(User,UserActivity).outerjoin(UserActivity,UserActivity.user_id==User.id).where(*conditions).order_by(UserActivity.registered_at.desc().nulls_last(),User.id).offset((page-1)*page_size).limit(page_size)).all()
    ids=[account.id for account,_ in rows];memberships=defaultdict(list)
    if ids:
        for uid,fid,data,member_role in db.execute(select(Member.user_id,Family.id,Family.data,Member.role).join(Family,Family.id==Member.family_id).where(Member.user_id.in_(ids)).order_by(Family.created,Family.id)):
            memberships[uid].append({'id':fid,'name':data.get('name','未命名家族'),'role':member_role})
    return {'total':total,'page':page,'pages':pages,'page_size':page_size,'items':[
        {'id':account.id,'name':account.name,'email':account.email,'admin':account.admin,
         'registered_at':activity.registered_at if activity else None,'last_login_at':activity.last_login_at if activity else None,
         'family_count':len(memberships[account.id]),'families':memberships[account.id]}
        for account,activity in rows
    ]}

class RegistrationSetting(BaseModel):
    enabled:bool
    version:int=Field(ge=0)

@app.put('/api/admin/registration')
def admin_registration(body:RegistrationSetting,user=Depends(site_admin),db=Depends(db_session)):
    with LOCK:
        config=registration_configuration(db)
        if body.version!=config['version']:fail(409,'注册设置已被更新，请刷新后再试')
        if body.enabled and not config['environment_allowed']:fail(409,'部署环境已关闭注册，请先调整服务器配置')
        data={'enabled':body.enabled,'version':body.version+1,'updated_by':user.id,'updated_at':now()}
        setting=db.get(SiteSetting,'registration')
        if setting:setting.data=data
        else:db.add(SiteSetting(key='registration',data=data))
        db.commit()
        return registration_configuration(db)

@app.post('/api/families')
def create_family(body:FamilyInput,user=Depends(current),db=Depends(db_session)):
    body.demo=False
    f=Family(data=body.model_dump());db.add(f);db.flush();db.add(Member(family_id=f.id,user_id=user.id,role='owner'));audit(db,f.id,user,'创建家族');db.commit()
    return {'id':f.id}

@app.put('/api/families/{fid}')
def change_family(fid:str,body:FamilyInput,user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,{'owner'})
    with LOCK:
        f=db.get(Family,fid)
        if body.cover and rec(db,fid,body.cover,'media').data.get('media_type')=='video':fail(422,'家族封面请选择图片')
        data=body.model_dump()
        # General settings must not overwrite a separately edited terminology dictionary.
        data['kinship_terms']=f.data.get('kinship_terms',{})
        data['kinship_version']=f.data.get('kinship_version',0)
        audit(db,fid,user,'更新家族设置',before=f.data,after=data);f.data=data;db.commit();return {'ok':True}

@app.put('/api/families/{fid}/kinship')
def change_kinship(fid:str,body:KinshipChange,user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,{'owner'})
    with LOCK:
        f=db.get(Family,fid)
        if f.data.get('kinship_version',0)!=body.version:fail(409,'称谓设置已更新，请重新载入后核对再保存')
        before=f.data.get('kinship_terms',{})
        f.data={**f.data,'kinship_terms':body.terms,'kinship_version':body.version+1}
        audit(db,fid,user,'批量更新家族称谓',before=before,after=body.terms)
        db.commit();return {'terms':body.terms,'version':body.version+1}

@app.get('/api/families/{fid}/state')
def state(fid:str,user=Depends(current),db=Depends(db_session)):
    role=access(db,fid,user);all_rows=records(db,fid);rows=visible_records(all_rows,role)
    if role=='contributor':rows += [r for r in all_rows if r.kind=='proposal' and r.data.get('author_id')==user.id]
    members=[{'id':m.id,'name':u.name,'role':m.role,'user_id':u.id} for m,u in db.execute(select(Member,User).join(User,Member.user_id==User.id).where(Member.family_id==fid)).all()]
    logs=list(db.scalars(select(Audit).where(Audit.family_id==fid).order_by(Audit.created.desc()).limit(200))) if role in EDITORS else []
    return {'family':{'id':fid,**db.get(Family,fid).data,'role':role},'records':enrich([pack(r) for r in rows]),'members':members,'audit':[{'id':a.id,'actor':a.actor,'action':a.action,'target':a.target,'created':a.created,'before':a.before,'after':a.after} for a in logs]}

def validate_record(db,fid,kind,data,rid=None):
    model={'person':PersonInput,'relation':RelationInput,'story':StoryInput}.get(kind)
    if not model:fail(400,'不支持的资料类型')
    data=model(**data).model_dump()
    if kind=='person' and data.get('avatar') and rec(db,fid,data['avatar'],'media').data.get('media_type')=='video':fail(422,'人物头像请选择图片')
    if kind=='story':
        for pid in data['person_ids']:rec(db,fid,pid,'person')
        data['media_ids']=list(dict.fromkeys(re.findall(r'\bmedia:([a-f0-9]{32})\b',data['body']))) if data['format']=='markdown' else []
        if len(data['media_ids'])>100:fail(422,'每篇档案最多引用 100 个媒体文件')
        for mid in data['media_ids']:
            attachment=db.get(Record,mid)
            if not attachment or attachment.family_id!=fid or attachment.kind!='media':fail(422,'正文引用的媒体不属于当前家族')
            if not attachment.deleted and data['privacy']=='family' and attachment.data.get('privacy')=='editors':fail(422,'正文引用了仅编辑可见的媒体，请调整档案或媒体的可见范围')
    if kind=='relation':
        a,b=data['from_id'],data['to_id']
        if a==b:fail(422,'不能把自己关联为自己的亲属')
        rec(db,fid,a,'person');rec(db,fid,b,'person')
        edges=[r for r in records(db,fid) if r.kind=='relation' and r.id!=rid]
        for r in edges:
            e=r.data
            if e['type']==data['type'] and ((e['from_id']==a and e['to_id']==b) or (data['type'] in SYMMETRIC_RELATIONS and e['from_id']==b and e['to_id']==a)):fail(409,'这条关系已存在')
        if data['type'] in PARENTS:
            links=defaultdict(list)
            for r in edges:
                if r.data['type'] in PARENTS:links[r.data['from_id']].append(r.data['to_id'])
            stack=[b];seen=set()
            while stack:
                node=stack.pop()
                if node==a:fail(422,'这条关系会使人物成为自己的祖先，请核对方向')
                if node not in seen:seen.add(node);stack.extend(links[node])
    return data

@app.post('/api/families/{fid}/records/{kind}')
def create_record(fid:str,kind:str,body:Change,user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,EDITORS)
    with LOCK:
        data=validate_record(db,fid,kind,body.data);r=Record(family_id=fid,kind=kind,data=data);db.add(r);db.flush();audit(db,fid,user,'新增'+{'person':'人物','relation':'关系','story':'档案'}[kind],r.id,after=data);db.commit();return pack(r)

@app.put('/api/families/{fid}/records/{rid}')
def edit_record(fid:str,rid:str,body:Change,user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,EDITORS)
    with LOCK:
        r=rec(db,fid,rid);data=validate_record(db,fid,r.kind,body.data,rid)
        before=r.data
        result=db.execute(update(Record).where(Record.id==rid,Record.family_id==fid,Record.version==body.version,Record.deleted==False).values(data=data,version=body.version+1,updated=now()))
        if result.rowcount!=1:db.rollback();fail(409,'资料已被其他人修改，请刷新后核对再保存')
        audit(db,fid,user,'修改资料',rid,before,data);db.commit();return {'ok':True}

@app.delete('/api/families/{fid}/records/{rid}')
def delete_record(fid:str,rid:str,version:int,user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,EDITORS)
    with LOCK:
        r=rec(db,fid,rid)
        if r.version!=version:fail(409,'资料版本已变化，请刷新')
        if r.kind=='person':
            for edge in records(db,fid):
                if edge.kind=='relation' and rid in {edge.data['from_id'],edge.data['to_id']}:fail(409,'请先移除此人物的亲属关系，再将人物移入回收站')
        if r.kind=='media':
            for p in records(db,fid):
                if p.kind=='person' and p.data.get('avatar')==rid:p.data={**p.data,'avatar':''};p.version+=1
            f=db.get(Family,fid)
            if f.data.get('cover')==rid:f.data={**f.data,'cover':''}
        r.deleted=True;r.version+=1;r.updated=now();audit(db,fid,user,'移入回收站',rid,before=r.data);db.commit();return {'ok':True}

@app.get('/api/families/{fid}/trash')
def trash(fid:str,user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,EDITORS);return [pack(r) for r in records(db,fid,True)]

@app.post('/api/families/{fid}/restore/{rid}')
def restore_record(fid:str,rid:str,user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,EDITORS)
    with LOCK:
        r=rec(db,fid,rid,deleted=True)
        if r.kind in KINDS:validate_record(db,fid,r.kind,r.data,r.id)
        r.deleted=False;r.version+=1;r.updated=now();audit(db,fid,user,'恢复资料',rid,after=r.data);db.commit();return {'ok':True}

@app.post('/api/families/{fid}/history/{aid}/restore')
def restore_version(fid:str,aid:str,body:Change,user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,EDITORS)
    with LOCK:
        a=db.scalar(select(Audit).where(Audit.id==aid,Audit.family_id==fid))
        if not a or not a.before:fail(404,'此记录没有可恢复的旧版本')
        r=rec(db,fid,a.target)
        if r.kind not in KINDS:fail(400,'此类记录请在对应页面恢复')
        if body.version!=r.version:fail(409,'当前资料已变化，请刷新')
        old=r.data;r.data=validate_record(db,fid,r.kind,a.before,r.id);r.version+=1;r.updated=now();audit(db,fid,user,'恢复历史版本',r.id,old,r.data);db.commit();return {'ok':True}

@app.post('/api/dates/convert')
def convert(body:FamilyDate):return date_info(body)

@app.post('/api/families/{fid}/invites')
def invite(fid:str,request:Request,role:str='viewer',user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,{'owner'});rate(request,'invite',30)
    if role not in {'editor','viewer','contributor'}:fail(422,'不支持的角色')
    code=secrets.token_urlsafe(24);db.add(Invitation(id=digest(code),family_id=fid,role=role,expires=int(time.time())+72*3600));audit(db,fid,user,'创建邀请');db.commit();return {'code':code,'expires_hours':72}

class Join(Credentials):code:str=Field(min_length=10,max_length=100)
@app.post('/api/join')
def join(body:Join,request:Request,response:Response,db=Depends(db_session)):
    rate(request,'join')
    with LOCK:
        inv=db.get(Invitation,digest(body.code))
        if not inv or inv.used or inv.expires<int(time.time()):fail(400,'邀请码无效、已使用或已过期')
        user=db.scalar(select(User).where(User.email==body.email));recovery=None
        if user:
            try:hasher.verify(user.password,body.password)
            except (VerifyMismatchError,InvalidHashError):fail(401,'邮箱或密码不正确')
        else:
            recovery=secrets.token_urlsafe(24);user=User(email=body.email,name=body.name,password=hasher.hash(body.password),recovery=digest(recovery));db.add(user);db.flush()
            db.add(UserActivity(user_id=user.id,registered_at=now()))
        if db.scalar(select(Member).where(Member.family_id==inv.family_id,Member.user_id==user.id)):fail(409,'你已经是该家族成员')
        db.add(Member(family_id=inv.family_id,user_id=user.id,role=inv.role));inv.used=True;audit(db,inv.family_id,user,'加入家族');db.commit()
        return {**establish(db,user,response),'recovery':recovery}

@app.put('/api/families/{fid}/members/{mid}')
def member_role(fid:str,mid:str,role:str,user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,{'owner'})
    if role not in {'editor','viewer','contributor','remove'}:fail(422,'不支持的角色')
    m=db.scalar(select(Member).where(Member.id==mid,Member.family_id==fid))
    if not m:fail(404,'成员不存在')
    if m.role=='owner':fail(400,'不能移除或降级家族所有者')
    if role=='remove':db.delete(m)
    else:m.role=role
    audit(db,fid,user,'调整成员权限',mid,after={'role':role});db.commit();return {'ok':True}

class ProposalInput(BaseModel):
    target:str=Field(default='',max_length=40)
    kind:str
    data:dict
    version:int=1
    reason:str=Field(min_length=1,max_length=1000)

@app.post('/api/families/{fid}/proposals')
def propose(fid:str,body:ProposalInput,user=Depends(current),db=Depends(db_session)):
    role=access(db,fid,user,EDITORS|{'contributor'})
    if body.target:
        target=rec(db,fid,body.target,body.kind)
        if target.id not in {r.id for r in visible_records(records(db,fid),role)}:fail(404,'资料不可访问')
    data=validate_record(db,fid,body.kind,body.data,body.target or None)
    if role not in EDITORS and data.get('privacy')=='editors':fail(403,'不能提报仅编辑可见的资料')
    if role not in EDITORS:
        visible={r.id for r in visible_records(records(db,fid),role)}
        linked=[data.get(k) for k in ('from_id','to_id','avatar') if data.get(k)]+data.get('person_ids',[])+data.get('media_ids',[])
        if any(x not in visible for x in linked):fail(404,'关联资料不可访问')
    r=Record(family_id=fid,kind='proposal',data={**body.model_dump(),'data':data,'author_id':user.id,'author':user.name,'status':'pending'});db.add(r);audit(db,fid,user,'提交修改建议');db.commit();return pack(r)

@app.post('/api/families/{fid}/proposals/{pid}/review')
def review(fid:str,pid:str,approve:bool,user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,EDITORS)
    with LOCK:
        p=rec(db,fid,pid,'proposal');v=p.data
        if v['status']!='pending':fail(409,'该建议已处理')
        if approve:
            data=validate_record(db,fid,v['kind'],v['data'],v['target'] or None)
            if v['target']:
                target=rec(db,fid,v['target'],v['kind'])
                if target.version!=v['version']:fail(409,'原始资料已更新，请重新核对并提报')
                old=target.data;target.data=data;target.version+=1;target.updated=now()
            else:
                target=Record(family_id=fid,kind=v['kind'],data=data);db.add(target);db.flush();old=None
            audit(db,fid,user,'采纳修改建议',target.id,old,data)
        p.data={**v,'status':'approved' if approve else 'rejected','reviewer':user.name};p.version+=1;db.commit();return {'ok':True}

def media_paths(fid,rid):return DATA/'media'/fid/rid
def readable_media(db,fid,rid,role):
    r=rec(db,fid,rid,'media');visible={x.id for x in visible_records(records(db,fid),role)}
    if rid not in visible:fail(404,'媒体不存在或无权查看')
    return r

def make_images(raw:bytes,path:Path):
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.format not in {'JPEG','PNG','WEBP'}:fail(422,'请上传 JPEG、PNG 或 WebP 图片')
            if im.width*im.height>30_000_000:fail(422,'图片超过 3000 万像素，请先缩小尺寸')
            im.load();image=ImageOps.exif_transpose(im).convert('RGB');width,height=image.size
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning):fail(422,'图片无法读取或像素过大')
    path.mkdir(parents=True,exist_ok=False)
    (path/'original').write_bytes(raw)
    thumb=image.copy();thumb.thumbnail((1600,1600));thumb.save(path/'display.jpg',quality=87)
    thumb.thumbnail((520,520));thumb.save(path/'thumb.jpg',quality=85)
    return width,height

def make_media(raw,path,filename='',content_type=''):
    if looks_like_video(raw,filename,content_type):return make_video(raw,path)
    if len(raw)>IMAGE_LIMIT:fail(413,'单张图片最大 12 MB')
    width,height=make_images(raw,path)
    return {'media_type':'image','width':width,'height':height}

@app.post('/api/families/{fid}/media')
async def upload_media(fid:str,file:UploadFile=File(...),metadata:str=Form('{}'),user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,EDITORS)
    try:meta=MediaMeta(**json.loads(metadata))
    except (json.JSONDecodeError,ValidationError):fail(422,'媒体说明格式不正确')
    for pid in meta.person_ids:rec(db,fid,pid,'person')
    raw=await file.read(VIDEO_LIMIT+1)
    if len(raw)>VIDEO_LIMIT:fail(413,'单个视频最大 64 MB，图片最大 12 MB')
    with LOCK:
        used=sum(r.data.get('size',0) for r in records(db,fid)+records(db,fid,True) if r.kind=='media')
        if used+len(raw)>FAMILY_MEDIA_LIMIT:fail(413,'此版本每个家族的图片与视频总空间上限为 128 MB')
        rid=uid();path=media_paths(fid,rid)
        try:
            info=make_media(raw,path,file.filename or '',file.content_type or '')
            data={**meta.model_dump(),**info,'title':meta.title or (file.filename or '家族记忆')[:150],'filename':Path(file.filename or 'media').name,'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
            r=Record(id=rid,family_id=fid,kind='media',data=data);db.add(r);audit(db,fid,user,'上传视频' if info['media_type']=='video' else '上传照片',rid,after=data);db.commit()
        except Exception:
            db.rollback()
            if path.exists():shutil.rmtree(path)
            raise
    return pack(r)

@app.get('/api/families/{fid}/media/{rid}/{variant}')
def get_media(fid:str,rid:str,variant:str,person:str='',user=Depends(current),db=Depends(db_session)):
    role=access(db,fid,user);r=readable_media(db,fid,rid,role)
    if variant not in {'original','display','thumb','avatar'}:fail(404,'图片规格不存在')
    if variant=='original' and role not in EDITORS:fail(403,'原图下载仅向编辑和所有者开放')
    if r.data.get('media_type')=='video':
        if variant=='avatar':fail(422,'视频不能作为头像')
        path=media_paths(fid,rid)/('thumb.jpg' if variant=='thumb' else 'original')
        if not path.is_file():fail(404,'媒体文件缺失，请从备份恢复')
        if variant=='thumb':return FileResponse(path,media_type='image/jpeg')
        if variant=='original':
            audit(db,fid,user,'下载原视频',rid);db.commit()
            return FileResponse(path,media_type='application/octet-stream',filename=r.data.get('filename','video.mp4'))
        return FileResponse(path,media_type=r.data['mime_type'])
    path=media_paths(fid,rid)/({'display':'display.jpg','thumb':'thumb.jpg','avatar':'avatar.jpg'}.get(variant,'original'))
    if variant=='avatar' and person:
        p=rec(db,fid,person,'person')
        if not visible_records([p],role):fail(404,'人物头像不可访问')
        if person in r.data.get('crops',{}):path=media_paths(fid,rid)/('avatar-'+person+'.jpg')
    if variant=='avatar' and not path.exists():path=media_paths(fid,rid)/'thumb.jpg'
    if not path.is_file():fail(404,'图片文件缺失，请从备份恢复')
    if variant=='original':
        audit(db,fid,user,'下载原图',rid);db.commit()
        return FileResponse(path,media_type='application/octet-stream',filename=r.data.get('filename','image'))
    return FileResponse(path,media_type='image/jpeg')

@app.put('/api/families/{fid}/media/{rid}')
def edit_media(fid:str,rid:str,body:MediaMeta,user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,EDITORS)
    for pid in body.person_ids:rec(db,fid,pid,'person')
    r=rec(db,fid,rid,'media');before=r.data;r.data={**r.data,**body.model_dump()};r.version+=1;audit(db,fid,user,'修改照片说明',rid,before,r.data);db.commit();return {'ok':True}

class Crop(BaseModel):
    x:float=Field(default=0,ge=0,le=1)
    y:float=Field(default=0,ge=0,le=1)
    size:float=Field(default=1,gt=0,le=1)
    rotation:int=Field(default=0)
    person_id:str=Field(default='',max_length=40)

def save_crop(path,body,filename='avatar.jpg'):
    with Image.open(path/'original') as src:
        img=ImageOps.exif_transpose(src).convert('RGB').rotate(-body.rotation,expand=True)
        w,h=img.size;size=max(1,int(min(w,h)*body.size));x=int((w-size)*body.x);y=int((h-size)*body.y)
        ImageOps.fit(img.crop((x,y,x+size,y+size)),(400,400)).save(path/filename,quality=90)

@app.post('/api/families/{fid}/media/{rid}/crop')
def crop_media(fid:str,rid:str,body:Crop,user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,EDITORS);r=rec(db,fid,rid,'media');path=media_paths(fid,rid)
    if r.data.get('media_type')=='video':fail(422,'视频不能裁剪为头像')
    if body.rotation not in {0,90,180,270}:fail(422,'只支持直角旋转')
    if body.person_id:
        rec(db,fid,body.person_id,'person')
        save_crop(path,body,'avatar-'+body.person_id+'.jpg')
        r.data={**r.data,'crops':{**r.data.get('crops',{}),body.person_id:body.model_dump(exclude={'person_id'})}}
        r.version+=1
    else:save_crop(path,body)
    audit(db,fid,user,'裁剪头像',rid);db.commit();return {'ok':True}

def archive_bytes(db,fid):
    rows=records(db,fid)+records(db,fid,True)
    logs=list(db.scalars(select(Audit).where(Audit.family_id==fid)))
    manifest={'format':'qinpu','version':1,'created':now(),'family':db.get(Family,fid).data,'records':[pack(r) for r in rows],'history':[{'actor':a.actor,'action':a.action,'target':a.target,'before':a.before,'after':a.after,'created':a.created} for a in logs]}
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for r in rows:
            if r.kind=='media':
                folder=media_paths(fid,r.id)
                if not (folder/'original').is_file():fail(409,'存在缺失原图，请恢复后再备份')
                z.write(folder/'original',f'media/{r.id}/original')
                if (folder/'avatar.jpg').is_file():z.write(folder/'avatar.jpg',f'media/{r.id}/avatar.jpg')
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False))
    return buf.getvalue()

def derive(password,salt):return Scrypt(salt=salt,length=32,n=2**15,r=8,p=1).derive(password.encode())
@app.post('/api/families/{fid}/backup')
def backup(fid:str,body:PasswordInput,user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,{'owner'})
    with LOCK:
        raw=archive_bytes(db,fid);salt=os.urandom(16);nonce=os.urandom(12)
        result=b'QINPU1'+salt+nonce+AESGCM(derive(body.password,salt)).encrypt(nonce,raw,b'qinpu-v1')
        audit(db,fid,user,'导出加密家族备份');db.commit()
    return Response(result,media_type='application/octet-stream',headers={'Content-Disposition':'attachment; filename="family.qinpu"'})

def open_backup(raw,password):
    if not raw.startswith(b'QINPU1'):fail(422,'请选择家谱加密备份文件（.qinpu）')
    try:
        payload=AESGCM(derive(password,raw[6:22])).decrypt(raw[22:34],raw[34:],b'qinpu-v1')
        z=zipfile.ZipFile(io.BytesIO(payload))
        entries=z.infolist()
        if len(entries)>40000 or sum(x.file_size for x in entries)>512*1024*1024:fail(413,'备份展开后超过 512 MB 或文件数量限制')
        if len(set(x.filename for x in entries))!=len(entries):fail(422,'备份包含重复文件')
        if z.getinfo('manifest.json').file_size>30*1024*1024:fail(413,'备份清单过大')
        m=json.loads(z.read('manifest.json'))
        if m.get('format')!='qinpu' or m.get('version')!=1:fail(422,'不支持此备份版本')
        rows=m['records']
        if len(rows)>30000 or len({r['id'] for r in rows})!=len(rows):fail(422,'备份资料数量或标识符无效')
        for r in rows:
            if not isinstance(r['id'],str) or len(r['id'])!=32 or any(c not in '0123456789abcdef' for c in r['id']):fail(422,'备份标识符无效')
            if r['kind'] not in KINDS|{'media','proposal'}:fail(422,'备份含未知资料类型')
        allowed={'manifest.json'}
        for r in rows:
            if r['kind']=='media':
                key=f'media/{r["id"]}/original';allowed|={key,f'media/{r["id"]}/avatar.jpg'}
                if z.getinfo(key).file_size>(VIDEO_LIMIT if r['data'].get('media_type')=='video' else IMAGE_LIMIT):fail(413,'备份中存在超限媒体')
                if hashlib.sha256(z.read(key)).hexdigest()!=r['data']['sha256']:fail(422,'图片完整性校验失败')
        if any(i.filename not in allowed for i in entries):fail(422,'备份中含未声明文件')
        FamilyInput(**m['family'])
        return z,m
    except HTTPException:raise
    except Exception:fail(422,'密码错误、备份损坏或格式不受支持')

@app.post('/api/restore-preview')
async def backup_preview(file:UploadFile=File(...),password:str=Form(...),user=Depends(current)):
    raw=await file.read(250*1024*1024+1)
    if len(raw)>250*1024*1024:fail(413,'备份最大 250 MB')
    z,m=open_backup(raw,password);z.close()
    return {'name':m['family']['name'],'created':m['created'],'counts':{kind:sum(r['kind']==kind for r in m['records']) for kind in ['person','relation','media','story']},'note':'将恢复为新的独立家族，不覆盖现有家族；账号和会话不会迁入。'}

@app.post('/api/restore')
async def backup_restore(file:UploadFile=File(...),password:str=Form(...),user=Depends(current),db=Depends(db_session)):
    raw=await file.read(250*1024*1024+1)
    if len(raw)>250*1024*1024:fail(413,'备份最大 250 MB')
    z,m=open_backup(raw,password);fid=uid();folder=DATA/'media'/fid
    mapping={r['id']:uid() for r in m['records']}
    def remap(data):
        if not isinstance(data,dict):return data
        v=data.copy()
        for key in ['from_id','to_id','avatar','cover','target']:
            if v.get(key):
                if v[key] not in mapping:fail(422,'备份含无法解析的资料关联')
                v[key]=mapping[v[key]]
        for key in ['person_ids','media_ids']:
            if key in v:
                if any(x not in mapping for x in v[key]):fail(422,'备份含无法解析的资料关联')
                v[key]=[mapping[x] for x in v[key]]
        if v.get('format')=='markdown' and isinstance(v.get('body'),str):
            v['body']=re.sub(r'\bmedia:([a-f0-9]{32})\b',lambda match:'media:'+mapping.get(match[1],match[1]),v['body'])
        return v
    with LOCK:
        try:
            family=FamilyInput(**remap(m['family'])).model_dump();family['name']=family['name'][:50]+' · 恢复'
            db.add(Family(id=fid,data=family));db.flush();db.add(Member(family_id=fid,user_id=user.id,role='owner'))
            prepared=[]
            for item in m['records']:
                data=remap(item['data']);kind=item['kind'];newid=mapping[item['id']]
                if kind=='person':data=PersonInput(**data).model_dump()
                elif kind=='story':data=StoryInput(**data).model_dump()
                elif kind=='relation':data=RelationInput(**data).model_dump()
                elif kind=='proposal':
                    data['author_id']='migrated';data['data']=remap(data['data'])
                elif kind=='media':
                    crops={mapping[pid]:Crop(**crop).model_dump(exclude={'person_id'}) for pid,crop in data.get('crops',{}).items() if pid in mapping}
                    metadata=MediaMeta(**data).model_dump();blob=z.read(f'media/{item["id"]}/original');info=make_media(blob,media_paths(fid,newid),data.get('filename',''))
                    data={**metadata,**info,'filename':Path(data.get('filename','media')).name,'size':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'crops':crops if info['media_type']=='image' else {}}
                    if info['media_type']=='video':crops={}
                    for pid,crop in crops.items():save_crop(media_paths(fid,newid),Crop(**crop),'avatar-'+pid+'.jpg')
                    av=f'media/{item["id"]}/avatar.jpg'
                    if av in z.namelist() and info['media_type']=='image':
                        with Image.open(io.BytesIO(z.read(av))) as im:ImageOps.fit(im.convert('RGB'),(400,400)).save(media_paths(fid,newid)/'avatar.jpg')
                row=Record(id=newid,family_id=fid,kind=kind,data=data,deleted=bool(item.get('deleted')),version=item.get('version',1));prepared.append(row);db.add(row)
            db.flush()
            for r in prepared:
                if not r.deleted and r.kind in KINDS:validate_record(db,fid,r.kind,r.data,r.id)
            for log in m.get('history',[])[:50000]:
                db.add(Audit(family_id=fid,actor=str(log['actor'])[:80],action=str(log['action'])[:100],target=mapping.get(log.get('target'),''),before=remap(log.get('before')),after=remap(log.get('after')),created=log['created']))
            audit(db,fid,user,'从加密备份恢复家族');db.commit()
        except Exception:
            db.rollback()
            if folder.exists():shutil.rmtree(folder)
            raise
        finally:z.close()
    return {'id':fid}

@app.get('/api/families/{fid}/export.csv')
def export_csv(fid:str,user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,EDITORS);buf=io.StringIO();writer=csv.writer(buf);writer.writerow(['姓名','别名','性别','世次','房支','生辰历法','出生年','出生月','出生日','农历闰月','出生地','生平','资料来源'])
    def safe(x):
        x=str(x or '');return "'"+x if x.startswith(('=','+','-','@','\t','\r')) else x
    for r in records(db,fid):
        if r.kind=='person':
            d=r.data;b=d.get('birth',{});writer.writerow([safe(x) for x in [d['name'],d.get('aliases'),d.get('gender'),d.get('generation'),d.get('branch'),b.get('calendar'),b.get('year'),b.get('month'),b.get('day'),str(b.get('leap',False)),d.get('birthplace'),d.get('bio'),d.get('source')]])
    audit(db,fid,user,'导出人物清单');db.commit();return Response(buf.getvalue().encode('utf-8-sig'),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="people.csv"'})

@app.post('/api/families/{fid}/import-csv')
async def import_csv(fid:str,file:UploadFile=File(...),commit:bool=Form(False),user=Depends(current),db=Depends(db_session)):
    access(db,fid,user,EDITORS);raw=await file.read(2*1024*1024+1)
    if len(raw)>2*1024*1024:fail(413,'CSV 最大 2 MB')
    try:reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')));rows=list(reader)
    except Exception:fail(422,'请上传 UTF-8 编码的 CSV 文件')
    if len(rows)>2000:fail(413,'单次最多导入 2000 人')
    if not reader.fieldnames or '姓名' not in reader.fieldnames:fail(422,'缺少“姓名”列；可先导出人物清单查看模板')
    existing={(r.data['name'],json.dumps(r.data.get('birth',{}),sort_keys=True)) for r in records(db,fid) if r.kind=='person'}
    valid=[];errors=[];duplicates=0
    for i,row in enumerate(rows,2):
        try:
            b={'calendar':row.get('生辰历法') or 'solar','year':int(row['出生年']) if row.get('出生年') else None,'month':int(row['出生月']) if row.get('出生月') else None,'day':int(row['出生日']) if row.get('出生日') else None,'leap':row.get('农历闰月','').lower()=='true'}
            p=PersonInput(name=row.get('姓名','').strip(),aliases=row.get('别名',''),gender=row.get('性别') or 'unknown',generation=row.get('世次',''),branch=row.get('房支',''),birth=b,birthplace=row.get('出生地',''),bio=row.get('生平',''),source=row.get('资料来源','')).model_dump()
            key=(p['name'],json.dumps(p['birth'],sort_keys=True))
            if key in existing:duplicates+=1;continue
            existing.add(key);valid.append(p)
        except Exception as e:errors.append({'line':i,'message':'姓名、性别或日期格式不正确'})
    if commit:
        if errors:fail(422,'请先修正预览中的错误行后再导入')
        for p in valid:db.add(Record(family_id=fid,kind='person',data=p))
        audit(db,fid,user,f'导入 {len(valid)} 位人物');db.commit()
    return {'count':len(valid),'duplicates':duplicates,'errors':errors,'preview':valid[:10],'committed':commit}

@app.get('/api/health')
def health():return {'ok':True,'version':'0.1.0'}

DIST=ROOT/'dist'
if DIST.exists():
    app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
@app.get('/{path:path}')
def frontend(path:str):
    if path.startswith('api/'):fail(404,'接口不存在')
    if (DIST/'index.html').exists():return FileResponse(DIST/'index.html')
    return JSONResponse({'message':'请先运行 npm install 和 npm run build'},503)
