import os

DB_PATH = "attendance.db"

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print("✅ Database deleted successfully!")
else:
    print("⚠️ Database file not found.")
