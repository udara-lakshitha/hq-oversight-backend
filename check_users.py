import sqlite3

# Connect to your local database instance
conn = sqlite3.connect("hq_oversight.db")
cursor = conn.cursor()

print("\n--- REGISTERED STUDENTS DATA ARCHIVE ---")
try:
    cursor.execute("SELECT id, name, email, phone_number, hashed_password FROM students;")
    rows = cursor.fetchall()
    for row in rows:
        print(f"ID: STU-{str(row[0])} | Name: {row[1]} | Email: {row[2]} | Mobile: {row[3]}")
        print(f"   ↳ Hashed Password Stored: {row[4]}\n")
except sqlite3.OperationalError:
    print("Database or students table does not exist yet. Run the FastAPI app first!")

conn.close()

# RESEND_API_KEY = "re_ULsGbKdS_2ser7aiBNktZDBnAMYYgotSu"