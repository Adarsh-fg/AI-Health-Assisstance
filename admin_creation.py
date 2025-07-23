import sqlite3

conn = sqlite3.connect('healthcare.db')
cursor = conn.cursor()
cursor.execute("UPDATE users SET is_admin = 1 WHERE email = ?", ('adarshai5770@gmail.com',))
conn.commit()
conn.close()
