import os, sys
from utils import db

if __name__ == "__main__":
  if len(sys.argv) != 2:
    print(f"usage: {sys.argv[0]} DISCORD_ID")
    exit(1)
  uid = int(sys.argv[1])
  username = os.getlogin()
  db.execute("INSERT OR REPLACE INTO users (id, username) VALUES (?, ?);", (uid, os.getlogin()))
  db.commit()
  print(f"successfully updated user {username}")

