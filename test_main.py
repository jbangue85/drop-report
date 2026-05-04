import sqlite3

conn = sqlite3.connect("data/dropreport.db")
c = conn.cursor()
c.execute("SELECT * FROM uploads ORDER BY uploaded_at DESC LIMIT 5")
print(c.fetchall())
