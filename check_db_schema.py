"""Check database schema."""
import sqlite3

conn = sqlite3.connect('miradb.db')
cursor = conn.cursor()

# Get users table schema
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()

print("=" * 60)
print("USERS TABLE SCHEMA")
print("=" * 60)
print()
print(f"{'ID':<5} {'Name':<30} {'Type':<15} {'Not Null':<10} {'Default':<20}")
print("-" * 90)

for col in columns:
    col_id, name, col_type, notnull, default_val, pk = col
    print(f"{col_id:<5} {name:<30} {col_type:<15} {notnull:<10} {str(default_val):<20}")

print()
print(f"Total columns: {len(columns)}")

conn.close()
