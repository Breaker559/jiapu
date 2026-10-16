import os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, String, Integer, JSON, Boolean, ForeignKey, UniqueConstraint, Index, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('QINPU_DATA', ROOT / 'data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
(DATA/'media').mkdir(exist_ok=True)
URL = os.environ.get('DATABASE_URL', 'sqlite:///' + (DATA/'qinpu.db').as_posix())
engine = create_engine(URL, connect_args={'check_same_thread':False,'timeout':30} if URL.startswith('sqlite') else {}, pool_pre_ping=True)
if URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def pragmas(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA journal_mode=WAL')

SessionLocal = sessionmaker(engine, expire_on_commit=False)
def uid(): return uuid4().hex
def now(): return datetime.now(timezone.utc).isoformat()
class Base(DeclarativeBase): pass

class User(Base):
    __tablename__='users'
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    email: Mapped[str]=mapped_column(String(200),unique=True)
    name: Mapped[str]=mapped_column(String(80))
    password: Mapped[str]=mapped_column(String(500))
    recovery: Mapped[str]=mapped_column(String(64))
    admin: Mapped[bool]=mapped_column(Boolean,default=False)

class Setup(Base):
    __tablename__='setup'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    version: Mapped[int]=mapped_column(Integer,default=1)

class UserActivity(Base):
    __tablename__='user_activity'
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),primary_key=True)
    # Existing accounts predate this information; never invent their registration date.
    registered_at: Mapped[str | None]=mapped_column(String(40),nullable=True)
    last_login_at: Mapped[str | None]=mapped_column(String(40),nullable=True)

class SiteSetting(Base):
    __tablename__='site_settings'
    key: Mapped[str]=mapped_column(String(40),primary_key=True)
    data: Mapped[dict]=mapped_column(JSON)

class LoginSession(Base):
    __tablename__='sessions'
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'))
    csrf: Mapped[str]=mapped_column(String(80))
    expires: Mapped[int]=mapped_column(Integer)

class Family(Base):
    __tablename__='families'
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    data: Mapped[dict]=mapped_column(JSON)
    created: Mapped[str]=mapped_column(String(40),default=now)

class Member(Base):
    __tablename__='members'
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    family_id: Mapped[str]=mapped_column(ForeignKey('families.id',ondelete='CASCADE'),index=True)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'))
    role: Mapped[str]=mapped_column(String(20))
    __table_args__=(UniqueConstraint('family_id','user_id'),)

class Record(Base):
    __tablename__='records'
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    family_id: Mapped[str]=mapped_column(ForeignKey('families.id',ondelete='CASCADE'))
    kind: Mapped[str]=mapped_column(String(20))
    data: Mapped[dict]=mapped_column(JSON)
    version: Mapped[int]=mapped_column(Integer,default=1)
    deleted: Mapped[bool]=mapped_column(Boolean,default=False)
    created: Mapped[str]=mapped_column(String(40),default=now)
    updated: Mapped[str]=mapped_column(String(40),default=now)
    __table_args__=(Index('ix_record_family_kind','family_id','kind','deleted'),)

class Audit(Base):
    __tablename__='audits'
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    family_id: Mapped[str]=mapped_column(ForeignKey('families.id',ondelete='CASCADE'),index=True)
    actor: Mapped[str]=mapped_column(String(80))
    action: Mapped[str]=mapped_column(String(100))
    target: Mapped[str]=mapped_column(String(32),default='')
    before: Mapped[dict | None]=mapped_column(JSON,nullable=True)
    after: Mapped[dict | None]=mapped_column(JSON,nullable=True)
    created: Mapped[str]=mapped_column(String(40),default=now)

class Invitation(Base):
    __tablename__='invitations'
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    family_id: Mapped[str]=mapped_column(ForeignKey('families.id',ondelete='CASCADE'))
    role: Mapped[str]=mapped_column(String(20))
    expires: Mapped[int]=mapped_column(Integer)
    used: Mapped[bool]=mapped_column(Boolean,default=False)

def init_db(): Base.metadata.create_all(engine)
