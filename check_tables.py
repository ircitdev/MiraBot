"""Check what tables exist in database."""
import sqlite3

conn = sqlite3.connect('miradb.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()

print("=" * 60)
print("TABLES IN DATABASE")
print("=" * 60)
print()

if tables:
    for i, (table_name,) in enumerate(tables, 1):
        print(f"{i}. {table_name}")

        # Get row count for each table
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"   Rows: {count}")
        except Exception as e:
            print(f"   Error: {e}")
        print()
else:
    print("No tables found!")

print(f"Total tables: {len(tables)}")

conn.close()
