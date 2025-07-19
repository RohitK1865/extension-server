from flask import Flask, request, jsonify
from flask_mysqldb import MySQL
from flask_cors import CORS
from datetime import datetime
import MySQLdb.cursors
import re

app = Flask(__name__)
CORS(app)  # Enable CORS for local development

# MySQL configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Moon@1865'
app.config['MYSQL_DB'] = 'tracklyst'

mysql = MySQL(app)

def validate_prn(prn):
    if not prn or len(prn.strip()) < 3:
        return False
    return re.match(r'^[A-Za-z0-9]+$', prn.strip())

def validate_platform(platform):
    valid_platforms = ['LeetCode', 'HackerRank', 'CodeChef', 'Codeforces', 'AtCoder']
    return platform in valid_platforms

def check_duplicate_submission(prn, title, platform):
    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT id FROM problems WHERE prn = %s AND title = %s AND platform = %s",
            (prn, title, platform)
        )
        result = cur.fetchone()
        cur.close()
        return result is not None
    except Exception as e:
        print(f"❌ Error checking duplicate: {e}")
        return False

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

        cur = mysql.connection.cursor()
        cur.execute("SELECT prn FROM students WHERE prn = %s", (prn,))
        existing = cur.fetchone()

        if existing:
            cur.close()
            return jsonify({"status": "error", "reason": "PRN already exists"}), 400

        cur.execute(
            "INSERT INTO students (prn, name, year, class) VALUES (%s, %s, %s, %s)",
            (prn, name, year, class_name or None)
        )
        mysql.connection.commit()
        cur.close()

        return jsonify({"status": "success", "message": "Student registered"}), 201

    except Exception as e:
        print(f"❌ Registration failed: {e}")
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

        if not validate_prn(prn):
            return jsonify({"status": "error", "reason": "Invalid PRN format"}), 400

        if not title:
            return jsonify({"status": "error", "reason": "Title is required"}), 400

        if difficulty not in ["Easy", "Medium", "Hard"]:
            return jsonify({"status": "error", "reason": f"Invalid difficulty: {difficulty}"}), 400

        if not validate_platform(platform):
            return jsonify({"status": "error", "reason": f"Invalid platform: {platform}"}), 400

        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if timestamp else datetime.now()
        except ValueError:
            dt = datetime.now()

        if check_duplicate_submission(prn, title, platform):
            return jsonify({"status": "duplicate", "message": "Problem already submitted"}), 200

        cur = mysql.connection.cursor()
        cur.execute("SELECT name FROM students WHERE prn = %s", (prn,))
        student = cur.fetchone()

        if not student:
            cur.close()
            return jsonify({"status": "error", "reason": "Student not found"}), 404

        cur.execute(
            "INSERT INTO problems (prn, title, difficulty, platform, solved_at) VALUES (%s, %s, %s, %s, %s)",
            (prn, title, difficulty, platform, dt)
        )
        mysql.connection.commit()
        problem_id = cur.lastrowid
        cur.close()

        return jsonify({
            "status": "success",
            "id": problem_id,
            "student": student[0],
            "message": f"Problem '{title}' submitted successfully"
        }), 201

    except MySQLdb.Error as e:
        return jsonify({"status": "error", "reason": "Database error"}), 500
    except Exception as e:
        return jsonify({"status": "error", "reason": "Internal server error"}), 500

@app.route('/stats/<prn>', methods=['GET'])
def get_stats(prn):
    try:
        if not validate_prn(prn):
            return jsonify({"status": "error", "reason": "Invalid PRN format"}), 400

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM students WHERE prn = %s", (prn,))
        student = cur.fetchone()

        if not student:
            cur.close()
            return jsonify({"status": "error", "reason": "Student not found"}), 404

        cur.execute("""
            SELECT 
                difficulty,
                platform,
                COUNT(*) as count
            FROM problems 
            WHERE prn = %s 
            GROUP BY difficulty, platform
        """, (prn,))
        stats = cur.fetchall()

        cur.execute("""
            SELECT title, difficulty, platform, solved_at 
            FROM problems 
            WHERE prn = %s 
            ORDER BY solved_at DESC 
            LIMIT 10
        """, (prn,))
        recent = cur.fetchall()
        cur.close()

        return jsonify({
            "status": "success",
            "student": student,
            "statistics": stats,
            "recent_submissions": recent
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "reason": "Internal server error"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT 1")
        cur.close()
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

if __name__ == '__main__':
    print("\U0001F680 Starting Tracklyst Backend Server...")
    print("\U0001F4CA Database: tracklyst")
    print("\U0001F310 Server: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
