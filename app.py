from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "lavina.db"

app = Flask(__name__)
app.secret_key = "CHANGEZ_CETTE_CLE_SECRETE_AVANT_PRODUCTION"


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
        updated_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    conn.commit()

    admin = conn.execute("SELECT id FROM users WHERE username = ?", ("admin",)).fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO users(username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "admin", datetime.now().isoformat(timespec="seconds"))
        )
        conn.commit()
    conn.close()


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


@app.route("/")
def home():
    if not current_user():
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        flash("Identifiant ou mot de passe incorrect.", "error")
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
    if user["role"] == "admin":
        diagnostics = conn.execute("""
            SELECT d.*, u.username
            FROM diagnostics d
            JOIN users u ON u.id = d.user_id
            ORDER BY d.updated_at DESC
        """).fetchall()
    else:
        diagnostics = conn.execute("""
            SELECT d.*, u.username
            FROM diagnostics d
            JOIN users u ON u.id = d.user_id
            WHERE d.user_id = ?
            ORDER BY d.updated_at DESC
        """, (user["id"],)).fetchall()
    conn.close()
    return render_template("dashboard.html", diagnostics=diagnostics)


@app.route("/users", methods=["GET", "POST"])
def users():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    if user["role"] != "admin":
        flash("Accès réservé à l’administrateur.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "user")
        if not username or not password:
            flash("Nom d’utilisateur et mot de passe obligatoires.", "error")
        else:
            try:
                conn = db()
                conn.execute(
                    "INSERT INTO users(username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                    (username, generate_password_hash(password), role, datetime.now().isoformat(timespec="seconds"))
                )
                conn.commit()
                conn.close()
                flash("Utilisateur créé avec succès.", "success")
            except sqlite3.IntegrityError:
                flash("Ce nom d’utilisateur existe déjà.", "error")

    conn = db()
    users_list = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("users.html", users=users_list)


@app.route("/diagnostic/new", methods=["GET", "POST"])
def new_diagnostic():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title", "Diagnostic LAVINA").strip() or "Diagnostic LAVINA"
        company = request.form.get("company", "").strip()
        site = request.form.get("site", "").strip()
        auditor = request.form.get("auditor", "").strip()
        now = datetime.now().isoformat(timespec="seconds")

        conn = db()
        cur = conn.execute("""
            INSERT INTO diagnostics(user_id, title, company, site, auditor, answers_json, total_score, total_max, percent, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, '{}', 0, 3000, 0, ?, ?)
        """, (user["id"], title, company, site, auditor, now, now))
        conn.commit()
        diag_id = cur.lastrowid
        conn.close()
        return redirect(url_for("edit_diagnostic", diagnostic_id=diag_id))

    return render_template("new_diagnostic.html")


def can_access_diagnostic(user, diagnostic):
    return diagnostic and (user["role"] == "admin" or diagnostic["user_id"] == user["id"])


@app.route("/diagnostic/<int:diagnostic_id>")
def edit_diagnostic(diagnostic_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = db()
    diagnostic = conn.execute("SELECT * FROM diagnostics WHERE id = ?", (diagnostic_id,)).fetchone()
    conn.close()

    if not can_access_diagnostic(user, diagnostic):
        flash("Diagnostic introuvable ou accès interdit.", "error")
        return redirect(url_for("dashboard"))

    return render_template("diagnostic.html", diagnostic=diagnostic)


@app.route("/api/diagnostic/<int:diagnostic_id>/save", methods=["POST"])
def save_diagnostic(diagnostic_id):
    user = current_user()
    if not user:
        return jsonify({"ok": False, "error": "Non connecté"}), 401

    conn = db()
    diagnostic = conn.execute("SELECT * FROM diagnostics WHERE id = ?", (diagnostic_id,)).fetchone()
    if not can_access_diagnostic(user, diagnostic):
        conn.close()
        return jsonify({"ok": False, "error": "Accès interdit"}), 403

    data = request.get_json(force=True)
    answers_json = json.dumps(data.get("answers", {}), ensure_ascii=False)
    total_score = int(data.get("total_score", 0))
    total_max = int(data.get("total_max", 3000))
    percent = float(data.get("percent", 0))
    now = datetime.now().isoformat(timespec="seconds")

    conn.execute("""
        UPDATE diagnostics
        SET answers_json = ?, total_score = ?, total_max = ?, percent = ?, updated_at = ?
        WHERE id = ?
    """, (answers_json, total_score, total_max, percent, now, diagnostic_id))
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "saved_at": now})


@app.route("/diagnostic/<int:diagnostic_id>/delete", methods=["POST"])
def delete_diagnostic(diagnostic_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = db()
    diagnostic = conn.execute("SELECT * FROM diagnostics WHERE id = ?", (diagnostic_id,)).fetchone()
    if not can_access_diagnostic(user, diagnostic):
        conn.close()
        flash("Suppression impossible.", "error")
        return redirect(url_for("dashboard"))

    conn.execute("DELETE FROM diagnostics WHERE id = ?", (diagnostic_id,))
    conn.commit()
    conn.close()
    flash("Diagnostic supprimé.", "success")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
