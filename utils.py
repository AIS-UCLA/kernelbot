import discord, logging, functools, sqlite3, operator
from enum import Enum
from typing import Iterable, TypeVar, Union

from config import DB

def init_logger():
  formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", datefmt="%b %d %H:%M:%S")
  handler = logging.StreamHandler()
  handler.setFormatter(formatter)
  logger = logging.getLogger(__name__)
  logger.setLevel(logging.INFO)
  logger.addHandler(handler)
  return logger, formatter

logger, formatter = init_logger()

# high byte: major version
# low byte: minor version
SCHEMA_VERSION = 0x0001

USERS_SCHEMA = """users (
  id       INTEGER PRIMARY KEY,       -- discord id
  username TEXT NOT NULL UNIQUE,      -- linux username
  perms    INTEGER NOT NULL DEFAULT 0 -- eg. can_create_competition
)"""
CHALLENGES_SCHEMA = """challenges (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,          -- unique id
  name       TEXT NOT NULL UNIQUE,                       -- name of challenge
  desc       TEXT,                                       -- description of challenge
  creator_id INTEGER NOT NULL REFERENCES users(discord), -- discord id of challenge creator
  tests      BLOB NOT NULL,                              -- safetensors
  flops      INTEGER,                                    -- estimated flopcount [optional]
  timing     REAL,                                       -- test timing [optional]
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"""
SUBMISSIONS_SCHEMA = """submissions (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,          -- unique id
  name       TEXT NOT NULL,                              -- submission name
  type       TEXT NOT NULL,                              -- eg. CUDA, PTX
  source     TEXT NOT NULL,                              -- source code
  comp_id    INTEGER NOT NULL REFERENCES challenges(id), -- competition id
  user_id    INTEGER NOT NULL REFERENCES users(discord), -- discord id of creator
  timing     REAL NOT NULL,                              -- test timing
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"""

def init_db():
  db = sqlite3.connect(DB)
  version = db.execute("PRAGMA user_version").fetchone()[0]
  assert version & 0xFF00 == SCHEMA_VERSION & 0xFF00, "database migration required"
  if version & 0xFF < SCHEMA_VERSION & 0xFF:
    logger.info(f"automatically upgrading database from v{version:X} to v{SCHEMA_VERSION:X}")
    cur = db.cursor()
    cur.execute(f"CREATE TABLE IF NOT EXISTS {USERS_SCHEMA};")
    cur.execute(f"CREATE TABLE IF NOT EXISTS {CHALLENGES_SCHEMA};")
    cur.execute(f"CREATE TABLE IF NOT EXISTS {SUBMISSIONS_SCHEMA};")
    cur.execute(f"PRAGMA user_version = {SCHEMA_VERSION};")
  return db

db = init_db()

class Perm(Enum):
  CREATE_CHALLENGE = 0b1

def check_user(*perms:Perm):
  def dec(func):
    @functools.wraps(func)
    async def wrapper(self, interation: discord.Interaction, *args, **kwargs):
      if (resp := db.execute("SELECT perms FROM users WHERE id = ?", (interation.user.id,)).fetchone()) is not None:
        if not all([bool(p.value & resp[0])  for p in perms]):
          await interation.response.send_message(f"missing permissions: {', '.join([p.name for p in perms])}", ephemeral=True)
        else: return await func(self, interation, *args, **kwargs)
      else: await interation.response.send_message("this command requires registration", ephemeral=True)
    return wrapper
  return dec

@functools.cache
def active_chals() -> list[str]:
  return [t[0] for t in db.execute("SELECT name FROM challenges;").fetchall()]

T = TypeVar("T")
def all_same(items:list[T]): return all(x == items[0] for x in items)
def prod(x:Iterable[T]) -> Union[T,int]: return functools.reduce(operator.mul, x, 1)
def fmt_time(tm:float) -> str: return f"{tm*1e6:.2f} us" if tm < 1e-3 else f"{tm*1e3:.2f} ms" if tm < 1 else f"{tm:.2f} s"
