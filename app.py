from flask import Flask, render_template, request, redirect, session, jsonify
import mysql.connector
from werkzeug.middleware.proxy_fix import ProxyFix
import os
from werkzeug.security import generate_password_hash, check_password_hash

# --------------------------------------------------
# FLASK APP SETUP
# --------------------------------------------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

# Fix session cookies behind Render's proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# SESSION COOKIE SETTINGS
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,   # Prevent JS access
    SESSION_COOKIE_SAMESITE='Lax'   # Recommended for login forms
)

# Enable secure cookies only on production (Render uses HTTPS)
if os.getenv("FLASK_ENV") == "production":
    app.config["SESSION_COOKIE_SECURE"] = True
else:
    app.config["SESSION_COOKIE_SECURE"] = False

# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------
def get_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQLHOST"),
        user=os.getenv("MYSQLUSER"),
        password=os.getenv("MYSQLPASSWORD"),
        database=os.getenv("MYSQLDATABASE"),
        port=int(os.getenv("MYSQLPORT")),
        ssl_disabled=True,
        autocommit=True
    )

# --------------------------------------------------
# CREATE TABLES (run manually once if needed)
# --------------------------------------------------
def create_tables():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(100),
        email VARCHAR(100) UNIQUE,
        password VARCHAR(255)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(100),
        patient_name VARCHAR(100),
        pickup_location VARCHAR(100),
        destination VARCHAR(100),
        contact_number VARCHAR(20)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contact_messages (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100),
        email VARCHAR(100),
        message TEXT
    )
    """)

    cursor.close()
    db.close()

# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------
@app.route("/")
def home():
    user = session.get("user")
    bookings = []

    if user:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM bookings WHERE username=%s", (user,))
        bookings = cursor.fetchall()
        cursor.close()
        db.close()

    return render_template("index.html", user=user, bookings=bookings)

# --------------------------------------------------
# REGISTER
# --------------------------------------------------
@app.route("/register", methods=["POST"])
def register():
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
            (
                request.form["username"],
                request.form["email"],
                generate_password_hash(request.form["password"])
            )
        )
    except mysql.connector.Error:
        cursor.close()
        db.close()
        return redirect("/?error=user_exists")

    cursor.close()
    db.close()
    return redirect("/")

# --------------------------------------------------
# LOGIN
# --------------------------------------------------
@app.route("/login", methods=["POST"])
def login():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM users WHERE email=%s",
        (request.form["email"],)
    )
    user = cursor.fetchone()

    if user and check_password_hash(user["password"], request.form["password"]):
        session["user"] = user["username"]
        print("✅ Logged in:", session["user"])  # Debug
    else:
        print("❌ Login failed")

    cursor.close()
    db.close()
    return redirect("/")

# --------------------------------------------------
# LOGOUT
# --------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# --------------------------------------------------
# CONTACT FORM
# --------------------------------------------------
@app.route("/contact", methods=["POST"])
def contact():
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "INSERT INTO contact_messages (name, email, message) VALUES (%s, %s, %s)",
        (
            request.form["name"],
            request.form["email"],
            request.form["message"]
        )
    )

    cursor.close()
    db.close()
    return redirect("/?success=1")

# --------------------------------------------------
# BOOKING
# --------------------------------------------------
@app.route("/book", methods=["POST"])
def book():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO bookings
        (username, patient_name, pickup_location, destination, contact_number)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        session["user"],
        request.form["patient_name"],
        request.form["pickup_location"],
        request.form["destination"],
        request.form["contact_number"]
    ))

    cursor.close()
    db.close()
    return redirect("/?success=1")

# --------------------------------------------------
# AJAX: GET BOOKINGS
# --------------------------------------------------
@app.route("/get_bookings")
def get_bookings():
    if "user" not in session:
        return jsonify([])

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM bookings WHERE username=%s", (session["user"],))
    data = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(data)

# --------------------------------------------------
# UPDATE BOOKING
# --------------------------------------------------
@app.route("/update_booking/<int:id>", methods=["POST"])
def update_booking(id):
    if "user" not in session:
        return "", 403

    data = request.get_json()
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        UPDATE bookings SET
        patient_name=%s,
        pickup_location=%s,
        destination=%s,
        contact_number=%s
        WHERE id=%s AND username=%s
    """, (
        data["patient_name"],
        data["pickup_location"],
        data["destination"],
        data["contact_number"],
        id,
        session["user"]
    ))

    cursor.close()
    db.close()
    return "", 204

# --------------------------------------------------
# DELETE BOOKING
# --------------------------------------------------
@app.route("/delete_booking/<int:id>", methods=["POST"])
def delete_booking(id):
    if "user" not in session:
        return "", 403

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM bookings WHERE id=%s AND username=%s",
        (id, session["user"])
    )
    cursor.close()
    db.close()
    return "", 204

# --------------------------------------------------
# DB CONNECTION TEST
# --------------------------------------------------
@app.route("/db-test")
def db_test():
    try:
        db = get_db()
        db.close()
        return "MySQL connected ✅"
    except Exception as e:
        return f"MySQL connection error: {e}"

# --------------------------------------------------
# DEBUG SESSION (Check logged-in user)
# --------------------------------------------------
@app.route("/whoami")
def whoami():
    return session.get("user", "No user logged in")

# --------------------------------------------------
# RUN APP
# --------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
