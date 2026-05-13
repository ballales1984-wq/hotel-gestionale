import sqlite3, os
db_path = r"D:\hotel gestionale\backend\hotel_abc.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print('Tables:', tables)
    for t in tables:
        cur.execute('SELECT COUNT(*) FROM ' + t)
        cnt = cur.fetchone()[0]
        print('  ' + t + ': ' + str(cnt) + ' rows')
    conn.close()
else:
    print('Database not found')