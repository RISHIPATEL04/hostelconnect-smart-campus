#!/usr/bin/env python3
"""HostelConnect prototype: standard-library HTTP API backed by SQLite."""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "work" / "hostelconnect.sqlite3"
SESSION_SECONDS = 60 * 60 * 24 * 14
PASSWORD = "hostel123"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    database_url=os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if database_url:
        import psycopg
        from psycopg.rows import dict_row
        pg=psycopg.connect(database_url,connect_timeout=8,sslmode="require",row_factory=dict_row)
        pg.prepare_threshold=None
        return PostgresConnection(pg)  # type: ignore[return-value]
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    return db


class PostgresConnection:
    """Small adapter so the local SQLite API can use hosted Postgres in Vercel."""
    def __init__(self, connection): self.connection=connection
    def execute(self, sql: str, params: tuple=()):
        try:return self.connection.execute(sql.replace("?","%s"),params)
        except Exception as e:
            if getattr(e,"sqlstate",None)=="23505":raise sqlite3.IntegrityError(str(e)) from e
            raise
    def commit(self):self.connection.commit()
    def close(self):self.connection.close()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180_000)
    return base64.b64encode(salt + digest).decode()


def verify_password(password: str, saved: str) -> bool:
    try:
        raw = base64.b64decode(saved)
        return hmac.compare_digest(raw[16:], hashlib.pbkdf2_hmac("sha256", password.encode(), raw[:16], 180_000))
    except (ValueError, TypeError):
        return False


def seed(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS profiles (
      id TEXT PRIMARY KEY, full_name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('student','warden','maintenance')),
      room_number TEXT, password_hash TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions (
      token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
      expires_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS notices (
      id TEXT PRIMARY KEY, created_by TEXT NOT NULL REFERENCES profiles(id), title TEXT NOT NULL,
      body TEXT NOT NULL, category TEXT NOT NULL, priority TEXT NOT NULL DEFAULT 'Normal',
      expires_at TEXT, archived_at TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS notice_reads (
      notice_id TEXT NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
      user_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
      read_at TEXT NOT NULL, PRIMARY KEY(notice_id,user_id)
    );
    CREATE TABLE IF NOT EXISTS notice_saves (
      notice_id TEXT NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
      user_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
      saved_at TEXT NOT NULL, PRIMARY KEY(notice_id,user_id)
    );
    CREATE TABLE IF NOT EXISTS complaints (
      id TEXT PRIMARY KEY, created_by TEXT NOT NULL REFERENCES profiles(id),
      category TEXT NOT NULL, room_number TEXT NOT NULL, description TEXT NOT NULL,
      photo_data TEXT, photo_mime TEXT, status TEXT NOT NULL DEFAULT 'Pending',
      assigned_to TEXT REFERENCES profiles(id), created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL, resolved_at TEXT
    );
    CREATE TABLE IF NOT EXISTS complaint_updates (
      id TEXT PRIMARY KEY, complaint_id TEXT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
      author_id TEXT NOT NULL REFERENCES profiles(id), status TEXT, message TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS notifications (
      id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
      title TEXT NOT NULL, body TEXT NOT NULL, complaint_id TEXT REFERENCES complaints(id) ON DELETE CASCADE,
      notice_id TEXT REFERENCES notices(id) ON DELETE CASCADE, created_at TEXT NOT NULL, read_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_complaints_creator ON complaints(created_by,created_at);
    CREATE INDEX IF NOT EXISTS idx_complaints_assignee ON complaints(assigned_to,status);
    CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id,created_at);
    """)
    people = [
      ("s1","Aarav Shah","aarav@hostel.demo","student","B-204"),
      ("s2","Mira Patel","mira@hostel.demo","student","A-108"),
      ("s3","Kabir Mehta","kabir@hostel.demo","student","B-311"),
      ("s4","Anaya Rao","anaya@hostel.demo","student","C-206"),
      ("s5","Ishaan Das","ishaan@hostel.demo","student","A-214"),
      ("s6","Diya Nair","diya@hostel.demo","student","C-118"),
      ("s7","Rohan Sen","rohan@hostel.demo","student","B-109"),
      ("w1","Priya Sharma","priya@hostel.demo","warden",None),
      ("w2","Dev Malhotra","dev@hostel.demo","warden",None),
      ("m1","Sanjay Kumar","sanjay@hostel.demo","maintenance",None),
      ("m2","Farah Ali","farah@hostel.demo","maintenance",None),
      ("m3","Manoj Verma","manoj@hostel.demo","maintenance",None),
    ]
    for p in people:
        db.execute("INSERT OR IGNORE INTO profiles VALUES(?,?,?,?,?,?,?)", (*p, hash_password(PASSWORD), now()))
    if db.execute("SELECT COUNT(*) AS count FROM notices").fetchone()["count"] == 0:
        items = [
          ("n-water","Water supply maintenance","The campus team will service the overhead water tank on Saturday from 10:00 AM to 12:30 PM. Please store enough water in advance.","Hostel","Urgent","w1",0),
          ("n-sports","Inter-hostel football registrations open","Build your team and sign up for the annual inter-hostel tournament. Registrations close this Friday. Contact the student sports committee to add your team.","Events","Normal","w2",1),
          ("n-quiet","Quiet hours during study week","Please keep music and conversations low after 9:30 PM in corridors and common rooms. The reading room will stay open until midnight.","Hostel","Normal","w1",2),
          ("n-library","Library hours extended","The central library reading room will remain open until 11 PM through Saturday for exam preparation.","Academic","Normal","w2",3),
          ("n-wifi","Wi-Fi maintenance tonight","Campus Wi-Fi may briefly disconnect between 11:30 PM and midnight while the network team applies an update.","Facilities","Urgent","w1",4),
        ]
        for nid,title,body,category,priority,author,days in items:
            created = datetime.fromtimestamp(time.time()-days*86400, timezone.utc).isoformat(timespec="seconds")
            db.execute("INSERT INTO notices VALUES(?,?,?,?,?,?,NULL,NULL,?)",(nid,author,title,body,category,priority,created))
    if db.execute("SELECT COUNT(*) AS count FROM complaints").fetchone()["count"] == 0:
        examples = [
          ("c-ac","s1","Electrical","B-204","Air conditioner is not cooling properly.","m1","In Progress"),
          ("c-tap","s2","Plumbing","A-108","The bathroom tap is leaking continuously.","m2","Pending"),
          ("c-wifi","s3","Wi-Fi","B-311","Wi-Fi signal drops frequently in this room.","m3","Resolved"),
        ]
        for cid,student,cat,room,desc,staff,status in examples:
            t=now(); resolved=t if status=="Resolved" else None
            db.execute("INSERT INTO complaints VALUES(?,?,?,?,?,NULL,NULL,?,?,?,?,?)",(cid,student,cat,room,desc,status,staff,t,t,resolved))
            db.execute("INSERT INTO complaint_updates VALUES(?,?,?,?,?,?)",("u-"+cid,cid,student,"Pending","Complaint submitted.",t))
            if status != "Pending":
                db.execute("INSERT INTO complaint_updates VALUES(?,?,?,?,?,?)",("u-"+cid+"-status",cid,staff,status,"Maintenance team updated the complaint.",t))
    db.commit()


def as_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


class Handler(BaseHTTPRequestHandler):
    server_version = "HostelConnect/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def send_json(self, data: object, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store")
        self.end_headers(); self.wfile.write(raw)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length","0"))
        if length > 6_000_000: raise ValueError("Request is too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def route(self) -> tuple[str,str]:
        parsed=urlparse(self.path)
        if parsed.path in ("/api", "/api/index.py") and "path" in parse_qs(parsed.query):
            api_path=parse_qs(parsed.query).get("path",[""])[0]
            return "/api/"+api_path,parsed.query
        return parsed.path, parsed.query

    def session_user(self, db: sqlite3.Connection) -> sqlite3.Row | None:
        cookie=SimpleCookie(self.headers.get("Cookie","")); token=cookie.get("hc_session")
        if not token:return None
        return db.execute("SELECT p.* FROM sessions s JOIN profiles p ON p.id=s.user_id WHERE s.token=? AND s.expires_at>?",(token.value,int(time.time()))).fetchone()

    def require_user(self, db: sqlite3.Connection) -> sqlite3.Row:
        user=self.session_user(db)
        if not user: raise PermissionError("Please sign in to continue")
        return user

    def require_role(self, user: sqlite3.Row, *roles: str) -> None:
        if user["role"] not in roles: raise PermissionError("You do not have permission to do that")

    def do_GET(self) -> None:
        path,query=self.route(); db=connect()
        try:
            if path.startswith("/api/"):
                user=self.session_user(db)
                if path=="/api/session":
                    self.send_json({"user":self.public_user(user)}); return
                if not user: raise PermissionError("Please sign in to continue")
                if path=="/api/notices":
                    rows=db.execute("""SELECT n.*,p.full_name AS author,
                      EXISTS(SELECT 1 FROM notice_reads r WHERE r.notice_id=n.id AND r.user_id=?) AS is_read
                      ,EXISTS(SELECT 1 FROM notice_saves s WHERE s.notice_id=n.id AND s.user_id=?) AS is_pinned
                      FROM notices n JOIN profiles p ON p.id=n.created_by
                      WHERE n.archived_at IS NULL AND (n.expires_at IS NULL OR n.expires_at>?)
                      ORDER BY n.priority='Urgent' DESC,n.created_at DESC""",(user["id"],user["id"],now())).fetchall()
                    self.send_json({"notices":[dict(r) for r in rows]}); return
                if path=="/api/complaints":
                    if user["role"]=="student": where="c.created_by=?"; args=(user["id"],)
                    elif user["role"]=="maintenance": where="c.assigned_to=?"; args=(user["id"],)
                    else: where="1=1"; args=()
                    rows=db.execute(f"""SELECT c.id,c.created_by,c.category,c.room_number,c.description,c.photo_mime,c.status,c.assigned_to,c.created_at,c.updated_at,c.resolved_at,s.full_name AS student_name,m.full_name AS assigned_name,
                      p.room_number AS student_room FROM complaints c
                      JOIN profiles s ON s.id=c.created_by LEFT JOIN profiles m ON m.id=c.assigned_to
                      JOIN profiles p ON p.id=c.created_by WHERE {where} ORDER BY c.updated_at DESC""",args).fetchall()
                    out=[]
                    for r in rows:
                        item=dict(r); item["updates"]=[dict(u) for u in db.execute("SELECT u.*,p.full_name AS author FROM complaint_updates u JOIN profiles p ON p.id=u.author_id WHERE complaint_id=? ORDER BY created_at",(r["id"],)).fetchall()]; out.append(item)
                    staff=[dict(r) for r in db.execute("SELECT id,full_name FROM profiles WHERE role='maintenance' ORDER BY full_name").fetchall()] if user["role"]=="warden" else []
                    self.send_json({"complaints":out,"staff":staff}); return
                if path=="/api/notifications":
                    rows=db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 40",(user["id"],)).fetchall()
                    self.send_json({"notifications":[dict(r) for r in rows]}); return
                if path.startswith("/api/photo/"):
                    cid=unquote(path.rsplit("/",1)[-1]); row=db.execute("SELECT photo_data,photo_mime,created_by,assigned_to FROM complaints WHERE id=?",(cid,)).fetchone()
                    if not row or not row["photo_data"]: self.send_error(404); return
                    if user["role"]=="student" and row["created_by"]!=user["id"]: raise PermissionError("Not allowed")
                    if user["role"]=="maintenance" and row["assigned_to"]!=user["id"]: raise PermissionError("Not allowed")
                    blob=base64.b64decode(row["photo_data"]); self.send_response(200); self.send_header("Content-Type",row["photo_mime"] or "application/octet-stream"); self.send_header("Content-Length",str(len(blob))); self.send_header("Cache-Control","private, max-age=300"); self.end_headers(); self.wfile.write(blob); return
                raise ValueError("API endpoint not found")
            rel=unquote(path.lstrip("/")) or "notice-board.html"
            if rel!="notice-board.html": self.send_error(404); return
            target=(ROOT/rel).resolve()
            if ROOT not in target.parents and target!=ROOT: self.send_error(403); return
            if not target.is_file(): self.send_error(404); return
            raw=target.read_bytes(); self.send_response(200); self.send_header("Content-Type",mimetypes.guess_type(str(target))[0] or "application/octet-stream"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-cache"); self.end_headers(); self.wfile.write(raw)
        except PermissionError as e:self.send_json({"error":str(e)},401)
        except (ValueError,json.JSONDecodeError) as e:self.send_json({"error":str(e)},400)
        except Exception as e: print("API error:",repr(e)); self.send_json({"error":"Something went wrong. Please try again."},500)
        finally: db.close()

    @staticmethod
    def public_user(user: sqlite3.Row | None) -> dict | None:
        if not user:return None
        return {k:user[k] for k in ("id","full_name","email","role","room_number")}

    def do_POST(self) -> None:
        path,_=self.route(); db=connect()
        try:
            data=self.read_json()
            if path=="/api/login":
                email=str(data.get("email","" )).strip().lower(); password=str(data.get("password",""))
                user=db.execute("SELECT * FROM profiles WHERE email=?",(email,)).fetchone()
                if not user or not verify_password(password,user["password_hash"]): self.send_json({"error":"Email or password is incorrect."},401); return
                token=secrets.token_urlsafe(32); db.execute("INSERT INTO sessions VALUES(?,?,?)",(token,user["id"],int(time.time())+SESSION_SECONDS)); db.commit()
                self.send_response(200); payload=json.dumps({"user":self.public_user(user)}).encode(); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(payload))); self.send_header("Set-Cookie",f"hc_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age={SESSION_SECONDS}"); self.end_headers(); self.wfile.write(payload); return
            if path=="/api/signup":
                name=str(data.get("full_name","")).strip(); email=str(data.get("email","")).strip().lower(); room=str(data.get("room_number","")).strip(); password=str(data.get("password",""))
                if len(name)<2 or len(name)>80:raise ValueError("Enter your name (2–80 characters)")
                if "@" not in email or len(email)>160:raise ValueError("Enter a valid email address")
                if not room or len(room)>20:raise ValueError("Enter your room number")
                if len(password)<8 or len(password)>128:raise ValueError("Password must be at least 8 characters")
                if db.execute("SELECT COUNT(*) AS count FROM profiles").fetchone()["count"]>=15:raise ValueError("This prototype is limited to 15 accounts")
                uid="stu-"+secrets.token_hex(6)
                try:db.execute("INSERT INTO profiles VALUES(?,?,?,?,?,?,?)",(uid,name,email,"student",room,hash_password(password),now()))
                except sqlite3.IntegrityError:raise ValueError("An account with that email already exists")
                token=secrets.token_urlsafe(32);db.execute("INSERT INTO sessions VALUES(?,?,?)",(token,uid,int(time.time())+SESSION_SECONDS));db.commit();created=db.execute("SELECT * FROM profiles WHERE id=?",(uid,)).fetchone()
                self.send_response(201);payload=json.dumps({"user":self.public_user(created)}).encode();self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(payload)));self.send_header("Set-Cookie",f"hc_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age={SESSION_SECONDS}");self.end_headers();self.wfile.write(payload);return
            user=self.require_user(db)
            if path=="/api/logout":
                cookie=SimpleCookie(self.headers.get("Cookie","")); token=cookie.get("hc_session")
                if token:db.execute("DELETE FROM sessions WHERE token=?",(token.value,)); db.commit()
                self.send_response(200); raw=b'{"ok":true}'; self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(raw))); self.send_header("Set-Cookie","hc_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"); self.end_headers(); self.wfile.write(raw); return
            if path=="/api/notices":
                self.require_role(user,"warden"); title=str(data.get("title","")).strip(); body=str(data.get("body","")).strip(); category=str(data.get("category","Hostel")); priority=str(data.get("priority","Normal"))
                if not title or not body: raise ValueError("Title and details are required")
                if len(title)>120 or len(body)>2000: raise ValueError("Notice is too long")
                if category not in ("Hostel","Events","Academic","Facilities","Lost & found"):raise ValueError("Choose a valid category")
                if priority not in ("Normal","Urgent"):raise ValueError("Choose a valid priority")
                nid="n-"+secrets.token_hex(8); created=now(); db.execute("INSERT INTO notices VALUES(?,?,?,?,?,?,?,NULL,?)",(nid,user["id"],title,body,category,priority,data.get("expires_at") or None,created))
                for student in db.execute("SELECT id FROM profiles WHERE role='student'").fetchall(): db.execute("INSERT INTO notifications VALUES(?,?,?,?,?,?,?,NULL)",("nt-"+secrets.token_hex(8),student["id"],"New campus notice",title,None,nid,created))
                db.commit(); self.send_json({"ok":True,"id":nid},201); return
            if path=="/api/complaints":
                self.require_role(user,"student"); category=str(data.get("category","")); description=str(data.get("description","")).strip()
                if category not in ("Electrical","Plumbing","Wi-Fi","Furniture","Other"):raise ValueError("Choose a valid category")
                if not description:raise ValueError("Please describe the issue")
                if len(description)>2000:raise ValueError("Description is too long")
                room=str(data.get("room_number") or user["room_number"] or "").strip()
                if not room:raise ValueError("Room number is required")
                photo=data.get("photo_data"); mime=data.get("photo_mime")
                if photo:
                    if not isinstance(photo,str) or len(photo)>5_000_000:raise ValueError("Photo must be smaller than 3.5 MB")
                    try:base64.b64decode(photo,validate=True)
                    except ValueError:raise ValueError("Invalid image attachment")
                    if not str(mime).startswith("image/"):raise ValueError("Attachment must be an image")
                cid="c-"+secrets.token_hex(6); t=now(); db.execute("INSERT INTO complaints VALUES(?,?,?,?,?,?,?,'Pending',NULL,?,?,NULL)",(cid,user["id"],category,room,description,photo,mime,t,t)); db.execute("INSERT INTO complaint_updates VALUES(?,?,?,?,?,?)",("u-"+secrets.token_hex(6),cid,user["id"],"Pending","Complaint submitted.",t))
                for w in db.execute("SELECT id FROM profiles WHERE role='warden'").fetchall():db.execute("INSERT INTO notifications VALUES(?,?,?,?,?,?,?,NULL)",("nt-"+secrets.token_hex(8),w["id"],"New repair complaint",f"{category} · Room {room}",cid,None,t))
                db.commit(); self.send_json({"ok":True,"id":cid},201); return
            if path.startswith("/api/complaints/") and path.endswith("/updates"):
                cid=unquote(path.split("/")[3]); c=db.execute("SELECT * FROM complaints WHERE id=?",(cid,)).fetchone()
                if not c:raise ValueError("Complaint not found")
                if user["role"]=="student" and c["created_by"]!=user["id"]:raise PermissionError("Not allowed")
                if user["role"]=="maintenance" and c["assigned_to"]!=user["id"]:raise PermissionError("Not allowed")
                self.require_role(user,"student","warden","maintenance"); msg=str(data.get("message","")).strip()
                if not msg:raise ValueError("Write an update first")
                t=now(); db.execute("INSERT INTO complaint_updates VALUES(?,?,?,?,?,?)",("u-"+secrets.token_hex(6),cid,user["id"],None,msg,t));
                recipients={c["created_by"]};
                if c["assigned_to"]:recipients.add(c["assigned_to"])
                for rid in recipients-{user["id"]}:db.execute("INSERT INTO notifications VALUES(?,?,?,?,?,?,?,NULL)",("nt-"+secrets.token_hex(8),rid,"Complaint update",msg,cid,None,t))
                db.execute("UPDATE complaints SET updated_at=? WHERE id=?",(t,cid));db.commit();self.send_json({"ok":True},201);return
            raise ValueError("API endpoint not found")
        except PermissionError as e:self.send_json({"error":str(e)},403)
        except (ValueError,json.JSONDecodeError) as e:self.send_json({"error":str(e)},400)
        except Exception as e:print("API error:",repr(e));self.send_json({"error":"Something went wrong. Please try again."},500)
        finally:db.close()

    def do_PATCH(self) -> None:
        path,_=self.route();db=connect()
        try:
            user=self.require_user(db);data=self.read_json();parts=path.strip("/").split("/");t=now()
            if parts==["api","profile"]:
                name=str(data.get("full_name",user["full_name"])).strip();room=str(data.get("room_number",user["room_number"] or "")).strip()
                if len(name)<2 or len(name)>80:raise ValueError("Enter your name (2–80 characters)")
                if user["role"]=="student" and (not room or len(room)>20):raise ValueError("Enter a valid room number")
                db.execute("UPDATE profiles SET full_name=?,room_number=? WHERE id=?",(name,room if user["role"]=="student" else user["room_number"],user["id"]));db.commit();updated=db.execute("SELECT * FROM profiles WHERE id=?",(user["id"],)).fetchone();self.send_json({"user":self.public_user(updated)});return
            if parts==["api","password"]:
                old=str(data.get("current_password",""));new=str(data.get("new_password",""));saved=db.execute("SELECT password_hash FROM profiles WHERE id=?",(user["id"],)).fetchone()["password_hash"]
                if not verify_password(old,saved):raise ValueError("Current password is incorrect")
                if len(new)<8 or len(new)>128:raise ValueError("New password must be at least 8 characters")
                db.execute("UPDATE profiles SET password_hash=? WHERE id=?",(hash_password(new),user["id"]));db.commit();self.send_json({"ok":True});return
            if len(parts)==3 and parts[:2]==["api","notices"] and parts[2]=="read":
                nid=str(data.get("notice_id",""));db.execute("INSERT INTO notice_reads VALUES(?,?,?) ON CONFLICT(notice_id,user_id) DO UPDATE SET read_at=excluded.read_at",(nid,user["id"],t));db.commit();self.send_json({"ok":True});return
            if len(parts)==4 and parts[:2]==["api","notices"] and parts[3]=="pin":
                nid=unquote(parts[2]);exists=db.execute("SELECT 1 FROM notices WHERE id=? AND archived_at IS NULL",(nid,)).fetchone()
                if not exists:raise ValueError("Notice not found")
                saved=db.execute("SELECT 1 FROM notice_saves WHERE notice_id=? AND user_id=?",(nid,user["id"])).fetchone()
                if saved:db.execute("DELETE FROM notice_saves WHERE notice_id=? AND user_id=?",(nid,user["id"]))
                else:db.execute("INSERT INTO notice_saves VALUES(?,?,?)",(nid,user["id"],t))
                db.commit();self.send_json({"ok":True,"is_pinned":not bool(saved)});return
            if len(parts)>=3 and parts[:2]==["api","notices"]:
                self.require_role(user,"warden");nid=unquote(parts[2]);db.execute("UPDATE notices SET archived_at=? WHERE id=?",(t,nid));db.commit();self.send_json({"ok":True});return
            if len(parts)>=3 and parts[:2]==["api","notifications"]:
                nid=unquote(parts[2]);db.execute("UPDATE notifications SET read_at=? WHERE id=? AND user_id=?",(t,nid,user["id"]));db.commit();self.send_json({"ok":True});return
            if len(parts)>=3 and parts[:2]==["api","complaints"]:
                cid=unquote(parts[2]);c=db.execute("SELECT * FROM complaints WHERE id=?",(cid,)).fetchone()
                if not c:raise ValueError("Complaint not found")
                status=data.get("status"); assignee=data.get("assigned_to")
                if user["role"]=="warden":
                    if status and status not in ("Pending","In Progress","Resolved"):raise ValueError("Choose a valid status")
                    if assignee and not db.execute("SELECT 1 FROM profiles WHERE id=? AND role='maintenance'",(assignee,)).fetchone():raise ValueError("Choose a maintenance team member")
                elif user["role"]=="maintenance":
                    if c["assigned_to"]!=user["id"]:raise PermissionError("You can only update complaints assigned to you")
                    if status not in ("In Progress","Resolved"):raise ValueError("Maintenance can set In Progress or Resolved")
                    assignee=c["assigned_to"]
                else:raise PermissionError("Students cannot change complaint status")
                new_status=status or c["status"];new_assignee=assignee if assignee is not None else c["assigned_to"]
                db.execute("UPDATE complaints SET status=?,assigned_to=?,updated_at=?,resolved_at=? WHERE id=?",(new_status,new_assignee,t,t if new_status=="Resolved" else None,cid))
                changed=[]
                if new_status!=c["status"]:changed.append((new_status,f"Status changed to {new_status}."))
                if new_assignee!=c["assigned_to"] and new_assignee:
                    staff=db.execute("SELECT full_name FROM profiles WHERE id=?",(new_assignee,)).fetchone();changed.append((None,f"Assigned to {staff['full_name']}."))
                for st,msg in changed:
                    db.execute("INSERT INTO complaint_updates VALUES(?,?,?,?,?,?)",("u-"+secrets.token_hex(6),cid,user["id"],st,msg,t))
                for rid in {c["created_by"],new_assignee}:
                    if rid and rid!=user["id"] and changed:db.execute("INSERT INTO notifications VALUES(?,?,?,?,?,?,?,NULL)",("nt-"+secrets.token_hex(8),rid,"Complaint updated",changed[-1][1],cid,None,t))
                db.commit();self.send_json({"ok":True});return
            raise ValueError("API endpoint not found")
        except PermissionError as e:self.send_json({"error":str(e)},403)
        except (ValueError,json.JSONDecodeError) as e:self.send_json({"error":str(e)},400)
        except Exception as e:print("API error:",repr(e));self.send_json({"error":"Something went wrong. Please try again."},500)
        finally:db.close()


def main() -> None:
    parser=argparse.ArgumentParser(description="Run the HostelConnect prototype API and web app")
    parser.add_argument("--host",default="127.0.0.1",help="Use 0.0.0.0 to share on your local Wi-Fi")
    parser.add_argument("--port",type=int,default=8000)
    args=parser.parse_args()
    db=connect()
    if not (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")):seed(db)
    db.close()
    httpd=ThreadingHTTPServer((args.host,args.port),Handler)
    print(f"HostelConnect ready at http://localhost:{args.port}")
    if args.host=="0.0.0.0":print("To use from a phone on the same Wi-Fi, open this computer's LAN IP on port",args.port)
    print("Demo password for all seeded accounts:",PASSWORD)
    try:httpd.serve_forever()
    except KeyboardInterrupt:print("\nStopping HostelConnect…")
    finally:httpd.server_close()


if __name__=="__main__":main()
