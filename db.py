import sqlite3
from enum import Enum

DB = "kernelbot.db"

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
  id        INTEGER PRIMARY KEY,
  name      TEXT NOT NULL,                              -- submission name
  type      TEXT NOT NULL,                              -- eg. CUDA, PTX
  source    TEXT NOT NULL,                              -- source code
  comp_id   INTEGER NOT NULL REFERENCES challenges(id), -- competition id
  user_id   INTEGER NOT NULL REFERENCES users(discord), -- discord id of creator
  timing    REAL NOT NULL,                              -- test timing
  transpose_a BOOLEAN DEFAULT 0,                        -- whether A was transposed
  transpose_b BOOLEAN DEFAULT 0,                        -- whether B was transposed
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"""

def init_db():
  db = sqlite3.connect(DB)
  version = db.execute("PRAGMA user_version").fetchone()[0]
  assert version & 0xFF00 == SCHEMA_VERSION & 0xFF00, "database migration required"
  if version & 0xFF < SCHEMA_VERSION & 0xFF:
    cur = db.cursor()
    cur.execute(f"CREATE TABLE IF NOT EXISTS {USERS_SCHEMA};")
    cur.execute(f"CREATE TABLE IF NOT EXISTS {CHALLENGES_SCHEMA};")
    cur.execute(f"CREATE TABLE IF NOT EXISTS {SUBMISSIONS_SCHEMA};")
    cur.execute(f"PRAGMA user_version = {SCHEMA_VERSION};")
  return db

db = init_db()

class Perm(Enum):
  CREATE_CHALLENGE = 0b1
  USER = 1
  ADMIN = 2


