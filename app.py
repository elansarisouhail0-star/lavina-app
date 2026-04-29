from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime

# -----------------------------
# CONFIG
# -----------------------------
APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "lavina.db"

# 🔥 IMPORTANT (corrige ton problème CSS)
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = "CHANGEZ_CETTE_CLE_SECRETE"

# -----------------------------
# DATABASE
# -----------------------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS diagnostics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        company TEXT,
        site TEXT,
        auditor TEXT,
        answers_json TEXT NOT NULL DEFAULT '{}',
        total_score INTEGER NOT NULL DEFAULT 0,
        total_max INTEGER NOT NULL DEFAULT 3000,
        percent REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)
    conn.commit()

    # Admin par défaut
    admin = conn.execute("SELECT id FROM users WHERE username = ?", ("admin",)).fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO users(username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "admin", datetime.now().isoformat())
        )
        conn.commit()

    conn.close()

# -----------------------------
# AUTH
# -----------------------------
def current_user():
    if "user_id" not in session:
        return None
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    conn.close()
    return user

@app.before_request
def ensure_db():
    init_db()

@app.context_processor
def inject_user():
    return {"current_user": current_user()}

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    if not current_user():
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))

        flash("Erreur login")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = db()
    diagnostics = conn.execute("SELECT * FROM diagnostics").fetchall()
    conn.close()

    return render_template("dashboard.html", diagnostics=diagnostics)

@app.route("/diagnostic/new", methods=["GET", "POST"])
def new_diagnostic():
    if request.method == "POST":
        conn = db()
        conn.execute("""
        INSERT INTO diagnostics(user_id, title, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """, (
            session["user_id"],
            request.form.get("title"),
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("dashboard"))

    return render_template("new_diagnostic.html")
@app.route("/users")
def users():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("users.html", users=[])


def can_access_diagnostic(user, diagnostic):
    return diagnostic and (user["role"] == "admin" or diagnostic["user_id"] == user["id"])


@app.route("/diagnostic/<int:diagnostic_id>")
def edit_diagnostic(diagnostic_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = db()
    diagnostic = conn.execute(
        "SELECT * FROM diagnostics WHERE id = ?", 
        (diagnostic_id,)
    ).fetchone()
    conn.close()

    if not diagnostic:
        flash("Diagnostic introuvable.", "error")
        return redirect(url_for("dashboard"))

    return render_template("diagnostic.html", diagnostic=diagnostic)


@app.route("/diagnostic/<int:diagnostic_id>/delete", methods=["POST"])
def delete_diagnostic(diagnostic_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = db()
    conn.execute("DELETE FROM diagnostics WHERE id = ?", (diagnostic_id,))
    conn.commit()
    conn.close()

    flash("Diagnostic supprimé.", "success")
    return redirect(url_for("dashboard"))
# -----------------------------
# MAIN (Railway)
# -----------------------------
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
