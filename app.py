from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import pymysql
import pymysql.cursors
import re
import os

app = Flask(__name__)
CORS(app)

# MySQL Configuration
DB_HOST = os.getenv("MYSQL_HOST", "localhost")
DB_USER = os.getenv("MYSQL_USER", "root")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "Moon@1865")
DB_NAME = os.getenv("MYSQL_DB", "tracklyst")

def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

def validate_prn(prn):
    return bool(prn and re.match(r'^[A-Za-z0-9]{3,}$', prn.strip()))

def validate_platform(platform):
    return platform in ['LeetCode', 'HackerRank', 'CodeChef', 'Codeforces', 'AtCoder']

@app.route('/register', methods=['POST'])
def register_student():
    try:
        data = request.get_json()
        prn = data.get("prn", "").strip()
        name = data.get("name", "").strip()
        year = data.get("year", "").strip().upper()
        class_name = data.get("class", "").strip()

        if not validate_prn(prn) or not name or year not in ["SY", "TY", "FINAL"]:
            return jsonify({"status": "error", "reason": "Invalid input"}), 400

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT prn FROM students WHERE prn = %s", (prn,))
            if cur.fetchone():
                return jsonify({"status": "error", "reason": "PRN already exists"}), 400

            cur.execute("INSERT INTO students (prn, name, year, class) VALUES (%s, %s, %s, %s)",
                        (prn, name, year, class_name or None))
            conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Student registered"}), 201
    except Exception as e:
        print("❌ Registration failed:", e)
        return jsonify({"status": "error", "reason": "Registration failed"}), 500

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.get_json()
        prn = data.get("prn", "").strip()
        title = data.get("title", "").strip()
        difficulty = data.get("difficulty", "").strip()
        platform = data.get("platform", "").strip()
        timestamp = data.get("timestamp")

        if not (validate_prn(prn) and title and difficulty in ["Easy", "Medium", "Hard"] and validate_platform(platform)):
            return jsonify({"status": "error", "reason": "Invalid input"}), 400

        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if timestamp else datetime.now()

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM problems WHERE prn = %s AND title = %s AND platform = %s",
                        (prn, title, platform))
            if cur.fetchone():
                return jsonify({"status": "duplicate", "message": "Problem already submitted"}), 200

            cur.execute("SELECT name FROM students WHERE prn = %s", (prn,))
            student = cur.fetchone()
            if not student:
                return jsonify({"status": "error", "reason": "Student not found"}), 404

            cur.execute(
                "INSERT INTO problems (prn, title, difficulty, platform, solved_at) VALUES (%s, %s, %s, %s, %s)",
                (prn, title, difficulty, platform, dt))
            conn.commit()
            problem_id = cur.lastrowid
        conn.close()

        return jsonify({
            "status": "success",
            "id": problem_id,
            "student": student['name'],
            "message": f"Problem '{title}' submitted successfully"
        }), 201
    except Exception as e:
        print("❌ Submission error:", e)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500

@app.route('/stats/<prn>', methods=['GET'])
def get_stats(prn):
    try:
        if not validate_prn(prn):
            return jsonify({"status": "error", "reason": "Invalid PRN format"}), 400

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students WHERE prn = %s", (prn,))
            student = cur.fetchone()
            if not student:
                return jsonify({"status": "error", "reason": "Student not found"}), 404

            cur.execute("""
                SELECT difficulty, platform, COUNT(*) as count
                FROM problems WHERE prn = %s
                GROUP BY difficulty, platform
            """, (prn,))
            stats = cur.fetchall()

            cur.execute("""
                SELECT title, difficulty, platform, solved_at
                FROM problems WHERE prn = %s
                ORDER BY solved_at DESC
                LIMIT 10
            """, (prn,))
            recent = cur.fetchall()
        conn.close()

        return jsonify({
            "status": "success",
            "student": student,
            "statistics": stats,
            "recent_submissions": recent
        }), 200
    except Exception as e:
        print("❌ Stats error:", e)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    try:
        conn = get_db_connection()
        conn.ping()
        conn.close()
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Tracklyst Backend Server...")
    print("📊 Database: tracklyst")
    print("🌐 Server: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
