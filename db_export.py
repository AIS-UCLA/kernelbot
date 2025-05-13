import sqlite3
import os
import subprocess
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('leaderboard_export')

MAIN_DB_PATH = "/home/gabe/kernelbot/kernelbot.db" 
EXPORT_DB_PATH = "/home/gabe/kernelbot/leaderboard.db"
REMOTE_HOST = "cherf.ais-ucla.org"
REMOTE_USER = "chris" 
REMOTE_PATH = "/www/kernelbot/" 

def export_leaderboard_data():
    """Export minimal leaderboard data (just users and times) to a separate SQLite database"""
    try:
        if os.path.exists(EXPORT_DB_PATH):
            os.remove(EXPORT_DB_PATH)
        
        export_conn = sqlite3.connect(EXPORT_DB_PATH)
        export_cur = export_conn.cursor()
        
        main_conn = sqlite3.connect(MAIN_DB_PATH)
        main_cur = main_conn.cursor()
        
        export_cur.execute('''
        CREATE TABLE challenges (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            desc TEXT
        )
        ''')
        
        export_cur.execute('''
        CREATE TABLE best_submissions (
            user_id TEXT NOT NULL,
            username TEXT,
            challenge_id INTEGER NOT NULL,
            kernel_name TEXT NOT NULL,
            kernel_type TEXT NOT NULL,
            timing REAL NOT NULL,
            submission_date TEXT,
            FOREIGN KEY (challenge_id) REFERENCES challenges(id)
        )
        ''')
        
        export_cur.execute('''
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        ''')
        export_cur.execute("INSERT INTO metadata VALUES (?, ?)", 
                          ("export_time", datetime.now().isoformat()))
        
        main_cur.execute("SELECT id, name, desc FROM challenges")
        challenges = main_cur.fetchall()
        export_cur.executemany("INSERT INTO challenges VALUES (?, ?, ?)", challenges)
        
        user_mapping = {}
        try:
            users = main_cur.execute("SELECT id, username FROM users").fetchall()
            for user_id, username in users:
                user_mapping[str(user_id)] = username
        except Exception as e:
            logger.warning(f"Error fetching user mappings: {e}")
        
        main_cur.execute("""
            WITH RankedSubmissions AS (
                SELECT 
                    s.user_id, 
                    c.id as challenge_id,
                    s.name as kernel_name, 
                    s.type as kernel_type, 
                    s.timing,
                    s.created_at,
                    ROW_NUMBER() OVER (PARTITION BY s.user_id, s.comp_id ORDER BY s.timing ASC) as rn
                FROM submissions s
                JOIN challenges c ON s.comp_id = c.id
                WHERE s.timing > 0
            )
            SELECT 
                user_id, 
                challenge_id,
                kernel_name, 
                kernel_type, 
                timing,
                created_at
            FROM RankedSubmissions
            WHERE rn = 1
            ORDER BY challenge_id, timing ASC
        """)
        
        best_submissions_raw = main_cur.fetchall()
        
        best_submissions = []
        for user_id, challenge_id, kernel_name, kernel_type, timing, created_at in best_submissions_raw:
            username = user_mapping.get(str(user_id), f"User-{user_id}")
            best_submissions.append((
                user_id, 
                username,
                challenge_id,
                kernel_name, 
                kernel_type, 
                timing,
                created_at
            ))
        
        export_cur.executemany("""
            INSERT INTO best_submissions 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, best_submissions)
        
        export_conn.commit()
        export_cur.execute("VACUUM")

        export_conn.close()
        main_conn.close()
        
        logger.info(f"Exported {len(challenges)} challenges and {len(best_submissions)} best submissions")
        return True
        
    except Exception as e:
        logger.error(f"Error exporting leaderboard data: {e}")
        return False

def upload_to_webhost():
    """Upload the exported database to the webhost using a two-step process with sudo"""
    try:
        ssh_key_path = os.path.expanduser("~/.ssh/cherf")
        
        temp_path = f"/home/{REMOTE_USER}/leaderboard.db"
        
        subprocess.run([
            "scp", "-i", ssh_key_path, EXPORT_DB_PATH, 
            f"{REMOTE_USER}@{REMOTE_HOST}:{temp_path}"
        ], check=True)
        
        logger.info(f"Successfully uploaded leaderboard database to temp location on {REMOTE_HOST}")
        
        subprocess.run([
            "ssh", "-i", ssh_key_path, f"{REMOTE_USER}@{REMOTE_HOST}",
            f"sudo mkdir -p {REMOTE_PATH} && sudo cp {temp_path} {REMOTE_PATH}/leaderboard.db && sudo chmod 644 {REMOTE_PATH}/leaderboard.db"
        ], check=True)
        
        logger.info(f"Successfully moved leaderboard database to final destination")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error uploading database to webhost: {e}")
        return False

if __name__ == "__main__":
    if export_leaderboard_data():
        upload_to_webhost()
