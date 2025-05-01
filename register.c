#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sqlite3.h>

#ifndef DB
#define DB "kernelbot.db"
#endif

int main(int argc, char **argv) {
  long long uid;
  char *username;
  sqlite3 *db;
  sqlite3_stmt *stmt;
  const char *sql = "INSERT OR REPLACE INTO users (id, username) VALUES (?, ?);";

  if (argc != 2) {
    fprintf(stderr, "usage: %s DISCORD_ID\n", argv[0]);
    return 1;
  }

  uid = atoll(argv[1]);
  if (!(username = getlogin())) {
    perror("getlogin");
    return 1;
  }

  if (sqlite3_open(DB, &db) != SQLITE_OK) {
    fprintf(stderr, "Cannot open database: %s\n", sqlite3_errmsg(db));
    sqlite3_close(db);
    return 1;
  }

  if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) {
    fprintf(stderr, "Failed to prepare statement: %s\n", sqlite3_errmsg(db));
    sqlite3_close(db);
    return 1;
  }

  sqlite3_bind_int64(stmt, 1, uid);
  sqlite3_bind_text(stmt, 2, username, -1, SQLITE_STATIC);

  if (sqlite3_step(stmt) != SQLITE_DONE) {
    fprintf(stderr, "Execution failed: %s\n", sqlite3_errmsg(db));
    sqlite3_finalize(stmt);
    sqlite3_close(db);
    return 1;
  }

  sqlite3_finalize(stmt);
  sqlite3_close(db);

  printf("successfully updated user %s\n", username);
  return 0;
}

