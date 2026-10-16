from typing import Literal
from pydantic import BaseModel, Field, field_validator
from .dates import FamilyDate

class Credentials(BaseModel):
    email: str = Field(min_length=3,max_length=200)
    password: str = Field(min_length=10,max_length=128)
    name: str = Field(default='家族管理员',min_length=1,max_length=50)
    demo: bool = True
    @field_validator('email')
    @classmethod
    def email_valid(cls,v):
        v=v.strip().lower()
        if '@' not in v or ' ' in v:raise ValueError('请填写有效邮箱')
        return v

class Registration(Credentials):
    name: str = Field(min_length=1,max_length=50)
    family_name: str = Field(min_length=1,max_length=60)
    demo: bool = False
    @field_validator('name','family_name')
    @classmethod
    def nonblank(cls,value):
        value=value.strip()
        if not value:raise ValueError('请填写称呼和家族名称')
        return value

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1,max_length=128)
    new_password: str = Field(min_length=10,max_length=128)

KinshipKey=Literal['marriage','past_marriage','father','mother','son','daughter','parent','child','husband','wife','spouse','partner','former_partner','coparent','other','legacy_partner','adoptive_father','adoptive_mother','adoptive_son','adoptive_daughter','adoptive_parent','adoptive_child','step_father','step_mother','step_son','step_daughter','step_parent','step_child','former_husband','former_wife','former_spouse']

def validate_kinship_terms(v):
    result={}
    for key,text in v.items():
        text=text.strip()
        if not text or len(text)>12 or any(ord(c)<32 or ord(c)==127 for c in text):
            raise ValueError('自定义称谓须为 1–12 个字符，不能包含换行或控制字符')
        result[key]=text
    return result

class KinshipChange(BaseModel):
    terms: dict[KinshipKey,str]=Field(default_factory=dict,max_length=31)
    version: int=Field(ge=0)
    _validate_terms=field_validator('terms')(validate_kinship_terms)

class FamilyInput(BaseModel):
    name: str = Field(min_length=1,max_length=60)
    surname: str = Field(default='',max_length=20)
    subtitle: str = Field(default='',max_length=120)
    hometown: str = Field(default='',max_length=100)
    hall: str = Field(default='',max_length=80)
    motto: str = Field(default='',max_length=200)
    description: str = Field(default='',max_length=3000)
    theme: Literal['teal','blue','violet']='teal'
    timezone: Literal['Asia/Shanghai']='Asia/Shanghai'
    demo: bool=False
    cover: str=''
    kinship_terms: dict[KinshipKey,str]=Field(default_factory=dict,max_length=31)
    kinship_version: int=Field(default=0,ge=0)
    _validate_terms=field_validator('kinship_terms')(validate_kinship_terms)

class PersonInput(BaseModel):
    name: str=Field(min_length=1,max_length=80)
    aliases: str=Field(default='',max_length=200)
    gender: Literal['male','female','unknown']='unknown'
    generation: str=Field(default='',max_length=60)
    branch: str=Field(default='',max_length=80)
    birth: FamilyDate=Field(default_factory=FamilyDate)
    death: FamilyDate=Field(default_factory=FamilyDate)
    living: bool=True
    birthplace: str=Field(default='',max_length=160)
    bio: str=Field(default='',max_length=10000)
    source: str=Field(default='',max_length=3000)
    privacy: Literal['family','editors']='family'
    avatar: str=Field(default='',max_length=40)
    anniversary_calendar: Literal['original','solar','lunar']='original'
    leap_policy: Literal['regular','only','both']='regular'
    missing_policy: Literal['last','next','skip']='last'

class RelationInput(BaseModel):
    from_id: str=Field(max_length=40)
    to_id: str=Field(max_length=40)
    type: Literal['parent','adoptive','step','parent_unknown','married','partner','former_spouse','former_partner','coparent','other','spouse']='parent'
    certainty: Literal['confirmed','uncertain']='confirmed'
    note: str=Field(default='',max_length=500)
    source: str=Field(default='',max_length=2000)

class StoryInput(BaseModel):
    title: str=Field(min_length=1,max_length=120)
    body: str=Field(default='',max_length=30000)
    format: Literal['plain','markdown']='plain'
    media_ids: list[str]=Field(default_factory=list,max_length=100)
    category: Literal['家族故事','家族大事','修谱笔记','资料来源']='家族故事'
    date: FamilyDate=Field(default_factory=FamilyDate)
    person_ids: list[str]=Field(default_factory=list,max_length=100)
    privacy: Literal['family','editors']='family'
    source: str=Field(default='',max_length=3000)

class Change(BaseModel):
    data: dict
    version: int=Field(default=1,ge=1)

class MediaMeta(BaseModel):
    title: str=Field(default='',max_length=150)
    description: str=Field(default='',max_length=2000)
    album: str=Field(default='家族相册',max_length=80)
    person_ids: list[str]=Field(default_factory=list,max_length=100)
    privacy: Literal['family','editors']='family'
    date: FamilyDate=Field(default_factory=FamilyDate)

class PasswordInput(BaseModel):
    password: str=Field(min_length=12,max_length=128)
