import os, sqlite3, secrets
from datetime import datetime, timezone
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
PAPERS_DIR = Path(os.environ.get("PAPERS_DIR", "papers"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "activity.sqlite3"

# Change the subject labels here. Put the matching PDFs in /papers:
# subject1.pdf, subject2.pdf, subject3.pdf
SUBJECTS = [
    {"name": "Subject 1", "file": "subject1.pdf"},
    {"name": "Subject 2", "file": "subject2.pdf"},
    {"name": "Subject 3", "file": "subject3.pdf"},
]
STUDENT_PIN = os.environ.get("STUDENT_PIN", "")

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            student_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            detail TEXT NOT NULL
        )""")
init_db()

def log_event(event_type, detail=""):
    with db() as con:
        con.execute(
            "INSERT INTO events(created_at, student_id, event_type, detail) VALUES(?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"),
             session.get("student_id", "student"), event_type[:80], detail[:300])
        )

def student_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("student_id"):
            return redirect(url_for("student_login"))
        return fn(*args, **kwargs)
    return wrapped

@app.route("/healthz")
def healthz():
    # Lightweight endpoint for Render health checks and external uptime monitors.
    return jsonify({"status": "ok"}), 200

@app.route("/")
def index():
    if session.get("student_id"):
        return redirect(url_for("test"))
    return redirect(url_for("student_login"))

@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        pin = request.form.get("pin", "")
        if not STUDENT_PIN:
            flash("Site setup incomplete: ask the owner to set STUDENT_PIN.", "error")
        elif secrets.compare_digest(pin, STUDENT_PIN):
            session.clear()
            session["student_id"] = "student"
            log_event("test_opened", "Student signed in")
            return redirect(url_for("test"))
        else:
            flash("Incorrect PIN. Try again.", "error")
    return render_template("login.html")

@app.route("/test")
@student_required
def test():
    papers = []
    for item in SUBJECTS:
        path = PAPERS_DIR / item["file"]
        papers.append({**item, "available": path.is_file()})
    return render_template("test.html", papers=papers)

@app.route("/paper/<int:paper_index>")
@student_required
def paper(paper_index):
    if paper_index < 0 or paper_index >= len(SUBJECTS):
        abort(404)
    filename = SUBJECTS[paper_index]["file"]
    path = PAPERS_DIR / filename
    if not path.is_file():
        abort(404, description="This subject PDF has not been added to the repository yet.")
    # Serve the PDF inline. This is convenient on mobile and desktop, but not DRM.
    from flask import send_from_directory
    return send_from_directory(str(PAPERS_DIR.resolve()), filename, mimetype="application/pdf", as_attachment=False)

@app.route("/event", methods=["POST"])
@student_required
def student_event():
    data = request.get_json(silent=True) or {}
    event_type = str(data.get("type", "unknown"))
    detail = str(data.get("detail", ""))
    allowed = {"tab_hidden", "page_visible", "page_exit", "copy_attempt", "context_menu", "fullscreen_exit"}
    if event_type not in allowed:
        return jsonify({"ok": False}), 400
    log_event(event_type, detail)
    return jsonify({"ok": True})

@app.route("/logout")
def logout():
    if session.get("student_id"):
        log_event("test_closed", "Student logged out")
    session.clear()
    return redirect(url_for("student_login"))

@app.errorhandler(413)
def too_large(_):
    return "Request too large.", 413

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
