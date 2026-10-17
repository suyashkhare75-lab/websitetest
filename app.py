import os, time, json, hmac, secrets, threading, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Flask, request, session, redirect, render_template, abort, jsonify, Response
import pymupdf
from jinja2 import ChoiceLoader, FileSystemLoader

BASE = os.path.dirname(os.path.abspath(__file__))

def _css():   # CSS seedha page mein daalte hain, alag link ki zaroorat nahi
    for p in (os.path.join(BASE, "static", "style.css"), os.path.join(BASE, "style.css")):
        if os.path.isfile(p):
            return open(p, encoding="utf-8").read()
    return ""
CSS = _css()

app = Flask(__name__, static_folder=None)
# templates/ folder ho ya sab files ek hi folder mein, dono chalega
app.jinja_env.loader = ChoiceLoader([FileSystemLoader(os.path.join(BASE, "templates")), FileSystemLoader(BASE)])
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(16)

@app.context_processor
def _inject(): return {"css": CSS}
app.permanent_session_lifetime = timedelta(hours=12)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

PASSWORD = os.environ.get("STUDENT_PASSWORD")
if not PASSWORD: raise RuntimeError("Render ke Environment mein STUDENT_PASSWORD set karo")
NAME = os.environ.get("STUDENT_NAME", "Student")
TG_TOKEN, TG_CHAT = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT_ID")
DURATION = int(os.environ.get("TEST_MINUTES", "60")) * 60      # har subject ka time
def papers_dir():   # papers/ folder, warna wahi folder jahan app.py hai
    p = os.path.join(BASE, "papers")
    return p if os.path.isdir(p) and any(f.lower().endswith(".pdf") for f in os.listdir(p)) else BASE
STATE_FILE = os.path.join(BASE, "state.json")
IST = timezone(timedelta(hours=5, minutes=30))
def save():
    try:
        with open(STATE_FILE, "w") as f: json.dump(T, f)
    except Exception: pass
try:   # restart ke baad bhi attempt yaad rahe
    T = json.load(open(STATE_FILE))
    for _t in T.values(): _t["last"] = time.time(); _t["lost"] = False
except Exception:
    T = {}

LABEL = {"tab": "Tab ya app badla", "blur": "Screen se focus hata (app switch / popup)",
         "close": "Page band ya refresh kiya", "resize": "Screen size badla (split-screen / floating app / rotate)",
         "key": "Copy / print / save / screenshot ki koshish"}

def notify(text):
    if not (TG_TOKEN and TG_CHAT): return
    def go():
        try:
            data = urllib.parse.urlencode({"chat_id": TG_CHAT, "text": text}).encode()
            urllib.request.urlopen(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data, timeout=10)
        except Exception: pass
    threading.Thread(target=go, daemon=True).start()

def subjects():
    d = papers_dir()
    return sorted(f[:-4] for f in os.listdir(d) if f.lower().endswith(".pdf"))

def pdf_path(sub):
    if sub not in subjects(): abort(404)
    return os.path.join(papers_dir(), sub + ".pdf")

def need_login(f):
    @wraps(f)
    def w(*a, **k):
        return f(*a, **k) if session.get("ok") else (jsonify(error="login"), 401)
    return w

def finish(sub, why="✅ Test khatam"):
    t = T.get(sub)
    if not t or t["done"]: return
    t["done"] = True; save()
    notify(f"{why}\nSubject: {sub}\nTime: {int((time.time() - t['start']) / 60)} min\nTotal violations: {t['n']}")

def live(sub):
    t = T.get(sub)
    if t and not t["done"] and time.time() - t["start"] > DURATION:
        finish(sub, "⏰ Time khatam")
    return t

@app.route("/")
def index():
    subs = []
    for s in subjects():
        t = live(s)
        subs.append({"name": s, "done": bool(t and t["done"]), "live": bool(t and not t["done"])})
    return render_template("index.html", logged=session.get("ok"), subs=subs, err=request.args.get("e"))

@app.post("/login")
def login():
    if hmac.compare_digest(request.form.get("password", ""), PASSWORD):
        session.permanent = True; session["ok"] = True
        return redirect("/")
    time.sleep(1.5)
    return redirect("/?e=Galat password")

@app.route("/test/<sub>")
def test(sub):
    if not session.get("ok"): return redirect("/")
    n_pages = len(pymupdf.open(pdf_path(sub)))
    t = live(sub)
    if t and t["done"]: return redirect("/?e=Ye subject ho chuka hai")
    if not t:
        T[sub] = {"start": time.time(), "last": time.time(), "n": 0, "ev": 0, "done": False, "lost": False}
        save()
        notify(f"📄 Paper khola: {sub}")
    else:
        notify(f"📄 Paper wapas khola: {sub}\nAb tak violations: {t['n']}")
    remaining = int(DURATION - (time.time() - T[sub]["start"]))
    return render_template("test.html", sub=sub, pages=n_pages, remaining=remaining)

@app.get("/page/<sub>/<int:i>")
@need_login
def page(sub, i):
    t = live(sub)
    if not t or t["done"]: abort(403)
    doc = pymupdf.open(pdf_path(sub))
    if i >= len(doc): abort(404)
    pg = doc[i]; w, h = pg.rect.width, pg.rect.height
    txt = f"{NAME} | {datetime.now(IST):%d-%b %H:%M}"   # har page par naam + time (screenshot/photo traceable)
    for y in range(40, int(h), 110):
        for x in range(-40, int(w), 230):
            pg.insert_text((x, y), txt, fontsize=15, color=(.45, .45, .45), fill_opacity=.28,
                           morph=(pymupdf.Point(x, y), pymupdf.Matrix(-28)))
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(1.7, 1.7))
    r = Response(pix.tobytes("jpeg", jpg_quality=72), mimetype="image/jpeg")
    r.headers["Cache-Control"] = "no-store"
    return r

@app.post("/api/event")
@need_login
def event():
    d = request.get_json(silent=True) or {}
    sub = d.get("sub"); t = live(sub)
    if not t or t["done"]: return jsonify(n=0, done=True)
    now = time.time(); t["last"] = now
    if now - t["ev"] > 1.5:      # ek action par blur + hidden dono aate hain, ek hi gino
        t["n"] += 1
        notify(f"⚠️ {LABEL.get(d.get('type'), d.get('type'))}\nSubject: {sub}\nTotal violations: {t['n']}")
    t["ev"] = now; save()
    return jsonify(n=t["n"], done=t["done"])

@app.post("/api/ping")
@need_login
def ping():
    sub = (request.get_json(silent=True) or {}).get("sub"); t = live(sub)
    if not t: return jsonify(done=True)
    t["last"] = time.time()
    if t["lost"] and not t["done"]:
        t["lost"] = False; notify(f"🟢 Wapas online aa gayi ({sub})")
    return jsonify(done=t["done"], remaining=int(DURATION - (time.time() - t["start"])))

@app.post("/api/done")
@need_login
def done():
    finish((request.get_json(silent=True) or {}).get("sub"))
    return jsonify(ok=True)

@app.get("/health")
def health(): return "ok"

def watchdog():   # 30 sec se ping nahi = app band / background / phone lock
    while True:
        time.sleep(10)
        for sub, t in list(T.items()):
            live(sub)
            if not t["done"] and not t["lost"] and time.time() - t["last"] > 30:
                t["lost"] = True
                notify(f"🔴 Page se connection toot gaya (app band ya background)\nSubject: {sub}\nTotal violations: {t['n']}")

def keepalive():  # Render free instance ko sone se rokta hai
    url = os.environ.get("RENDER_EXTERNAL_URL")
    while url:
        time.sleep(600)
        try: urllib.request.urlopen(url + "/health", timeout=20)
        except Exception: pass

threading.Thread(target=watchdog, daemon=True).start()
threading.Thread(target=keepalive, daemon=True).start()

if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5000)))
