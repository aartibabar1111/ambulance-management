from flask import Flask, render_template, request, redirect, session , flash , jsonify
import mysql.connector
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

# Database connection
db = None
cursor = None

def init_db():
    global db, cursor
    if db is None or not db.is_connected():
        db = mysql.connector.connect(
            host=os.getenv("MYSQLHOST"),
            user=os.getenv("MYSQLUSER"),
            password=os.getenv("MYSQLPASSWORD"),
            database=os.getenv("MYSQLDATABASE"),
            port=int(os.getenv("MYSQLPORT", 3306))
        )
        cursor = db.cursor(dictionary=True)
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
        db.commit()

init_db()

# Routes


@app.route("/")
def home():
    init_db()
    user = session.get("user")
    
    bookings = []
    if user:
        cursor.execute("SELECT * FROM bookings WHERE username=%s", (user,))
        bookings = cursor.fetchall()
    
    return render_template("index.html", user=user, bookings=bookings)


@app.route("/login", methods=["POST"])
def login():
    init_db()
    email = request.form.get("email")
    password = request.form.get("password")
    cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
    user = cursor.fetchone()
    if user:
        session["user"] = user["username"]
    return redirect("/")

@app.route("/register", methods=["POST"])
def register():
    init_db()
    username = request.form.get("username")
    email = request.form.get("email")
    password = request.form.get("password")
    cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, password))
    db.commit()
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/contact", methods=["POST"])
def contact():
    init_db()
    if not cursor:
        return "Database connection error", 500

    # Get data from form
    name = request.form.get("name")
    email = request.form.get("email")
    message = request.form.get("message")

    # Insert into database
    sql = "INSERT INTO contact_messages (name, email, message) VALUES (%s, %s, %s)"
    cursor.execute(sql, (name, email, message))
    db.commit()

    # Redirect with success query parameter
    return redirect("/?success=1")


# ---------------- Book Ambulance ----------------
@app.route("/book", methods=["POST"])
def book():
    if "user" not in session:
        return redirect("/")
    username = session["user"]
    patient_name = request.form["patient_name"]
    pickup = request.form["pickup_location"]
    destination = request.form["destination"]
    contact = request.form["contact_number"]
    cursor.execute("INSERT INTO bookings (username, patient_name, pickup_location, destination, contact_number) VALUES (%s,%s,%s,%s,%s)",
                   (username, patient_name, pickup, destination, contact))
    db.commit()
    return redirect("/?success=1")

@app.route("/get_bookings")
def get_bookings():
    if "user" not in session:
        return jsonify([])
    cursor.execute("SELECT * FROM bookings WHERE username=%s", (session["user"],))
    return jsonify(cursor.fetchall())

@app.route("/update_booking/<int:id>", methods=["POST"])
def update_booking(id):
    if "user" not in session:
        return '', 403

    data = request.get_json()
    if not data:
        return "No data received", 400

    patient_name = data.get("patient_name")
    pickup = data.get("pickup_location")
    destination = data.get("destination")
    contact = data.get("contact_number")

    if not all([patient_name, pickup, destination, contact]):
        return "Missing fields", 400

    cursor.execute("""
        UPDATE bookings 
        SET patient_name=%s, pickup_location=%s, destination=%s, contact_number=%s
        WHERE id=%s AND username=%s
    """, (patient_name, pickup, destination, contact, id, session["user"]))
    db.commit()
    return '', 204


# --- Delete booking ---
@app.route("/delete_booking/<int:id>", methods=["POST"])
def delete_booking(id):
    if "user" not in session:
        return '', 403
    cursor.execute("DELETE FROM bookings WHERE id=%s AND username=%s", (id, session["user"]))
    db.commit()
    return '', 204

if __name__ == "__main__":
    app.run(debug=True)
