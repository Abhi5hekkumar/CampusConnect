from dotenv import load_dotenv
load_dotenv()

import os

def get_config(name: str, default: str = "") -> str:
    """Read Streamlit Cloud Secrets first, then fall back to local environment."""
    try:
        value = st.secrets.get(name, None)
    except Exception:
        value = None
    if value is None or str(value) == "":
        value = os.getenv(name, default)
    return str(value if value is not None else default)
import base64
import hmac
import secrets
import sqlite3
from io import BytesIO
from pathlib import Path

import streamlit as st
from groq import Groq
import speech_recognition as sr
from gtts import gTTS
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment
import pandas as pd
import bcrypt

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "students.db"
FAQ_PATH = BASE_DIR / "faqs.csv"

st.set_page_config(page_title="GNIT College Help Desk", page_icon="🎓", layout="wide")
st.markdown("""
<style>
:root { --brand:#1a73e8; --brand-dark:#1558b0; --ink:#202124; --muted:#5f6368; --line:#dadce0; --surface:#fff; --canvas:#f8fafd; }
.stApp { background:var(--canvas); color:var(--ink); }
.block-container { max-width: 1440px; padding: 2rem 2.4rem 3rem; }
h1,h2,h3 { color:var(--ink); letter-spacing:-.025em; }
h1 { font-size:2.25rem !important; font-weight:650 !important; }
h2 { font-weight:620 !important; }
p, label, .stMarkdown { color:var(--ink); }
.portal-brand { font-size:.78rem; letter-spacing:.09em; text-transform:uppercase; color:var(--muted); font-weight:700; margin-bottom:.45rem; }
div[data-testid="stForm"] { border:1px solid var(--line); border-radius:20px; padding:1.5rem; background:#fff; box-shadow:0 1px 2px rgba(60,64,67,.08); }
div[data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--line) !important; border-radius:18px !important; background:#fff; }
div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea, div[data-testid="stSelectbox"] [data-baseweb="select"] { border-radius:10px; }
div.stButton > button, div.stFormSubmitButton > button { border-radius:999px; min-height:2.8rem; font-weight:600; padding:.45rem 1.25rem; transition:all .15s ease; }
div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] { background:var(--brand); border-color:var(--brand); color:#fff; }
div.stButton > button[kind="primary"]:hover, div.stFormSubmitButton > button[kind="primary"]:hover { background:var(--brand-dark); border-color:var(--brand-dark); }
div[data-testid="stTabs"] [data-baseweb="tab-list"] { gap:.35rem; border-bottom:1px solid var(--line); flex-wrap:wrap; }
div[data-testid="stTabs"] button[data-baseweb="tab"] { padding:.7rem 1rem; font-weight:550; }
div[data-testid="stTabs"] button[aria-selected="true"] { color:var(--brand); }
div[data-testid="stMetric"] { border:1px solid var(--line); border-radius:16px; background:#fff; padding:1rem 1.15rem; box-shadow:0 1px 2px rgba(60,64,67,.05); }
div[data-testid="stChatMessage"] { background:#fff; border:1px solid #e8eaed; border-radius:16px; padding:1rem; }
[data-testid="stSidebar"] { background:#f1f5f9; border-right:1px solid var(--line); }
[data-testid="stSidebar"] .block-container { padding:1.2rem .9rem; }
[data-testid="stSidebar"] div.stButton > button { border-radius:12px; text-align:left; min-height:2.7rem; font-size:.92rem; }
[data-testid="stImage"] img { max-width:100%; height:auto; object-fit:cover; border-radius:14px; }
div[data-testid="stFileUploader"] { min-width:0; }
[data-testid="stAlert"] { border-radius:14px; }
.portal-hero { padding:1.4rem 1.6rem; border:1px solid #d2e3fc; border-radius:20px; background:linear-gradient(120deg,#eaf2fe,#f8fbff); margin-bottom:1rem; }
.portal-subtitle { color:var(--muted); font-size:.98rem; }
.sidebar-user { padding:.8rem; border-radius:14px; background:#fff; border:1px solid var(--line); margin-bottom:.75rem; }
.public-info-scroll { max-height:220px; overflow-y:auto; line-height:1.6; }
@media (max-width: 768px) { .block-container {padding:1rem .8rem 2rem;} h1 {font-size:1.8rem !important;} }
</style>
""", unsafe_allow_html=True)

API_KEY = get_config("GROQ_API_KEY").strip()
if not API_KEY:
    st.error("Groq API key missing. Add GROQ_API_KEY under Streamlit App Settings → Secrets.")
    st.stop()
client = Groq(api_key=API_KEY)

if not FAQ_PATH.exists():
    st.error("faqs.csv was not found beside app.py.")
    st.stop()
faq_df = pd.read_csv(FAQ_PATH)

# ---------------- Database and authentication ----------------
def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Add authentication fields without deleting existing students or timetable rows."""
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                fee_status TEXT,
                course TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS timetables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course TEXT NOT NULL,
                day TEXT NOT NULL,
                schedule TEXT NOT NULL
            )
        """)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(students)")}
        if "email" not in columns:
            conn.execute("ALTER TABLE students ADD COLUMN email TEXT")
        if "role" not in columns:
            conn.execute("ALTER TABLE students ADD COLUMN role TEXT NOT NULL DEFAULT 'student'")
        if "active" not in columns:
            conn.execute("ALTER TABLE students ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
        if "profile_picture" not in columns:
            conn.execute("ALTER TABLE students ADD COLUMN profile_picture BLOB")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_students_email ON students(email) WHERE email IS NOT NULL AND email <> ''")
        conn.execute("CREATE TABLE IF NOT EXISTS faculty (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, department TEXT, designation TEXT, email TEXT, phone TEXT, office TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS holidays (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, title TEXT NOT NULL, details TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS library_books (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, author TEXT, course TEXT, total_copies INTEGER NOT NULL DEFAULT 1, available_copies INTEGER NOT NULL DEFAULT 1)")
        conn.execute("CREATE TABLE IF NOT EXISTS campus_locations (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, building TEXT, room TEXT, details TEXT, map_url TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, details TEXT NOT NULL, posted_on TEXT NOT NULL DEFAULT CURRENT_DATE)")
        conn.execute("CREATE TABLE IF NOT EXISTS assignments (id INTEGER PRIMARY KEY AUTOINCREMENT, course TEXT NOT NULL, title TEXT NOT NULL, details TEXT, due_date TEXT NOT NULL, created_on TEXT NOT NULL DEFAULT CURRENT_DATE)")
        conn.execute("CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, class_date TEXT NOT NULL, course TEXT, status TEXT NOT NULL CHECK(status IN ('Present','Absent','Late','Excused')), notes TEXT, UNIQUE(username,class_date,course))")
        conn.execute("CREATE TABLE IF NOT EXISTS student_queries (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, category TEXT NOT NULL, subject TEXT NOT NULL, details TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Open', admin_response TEXT, created_on TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_on TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        conn.execute("CREATE TABLE IF NOT EXISTS password_reset_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, email TEXT, status TEXT NOT NULL DEFAULT 'Pending', created_on TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, resolved_on TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS faculty_access_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL, username TEXT NOT NULL UNIQUE, email TEXT NOT NULL, department TEXT NOT NULL, designation TEXT NOT NULL, password_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending', created_on TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, reviewed_on TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS college_info (section TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL DEFAULT '')")
        conn.execute("CREATE TABLE IF NOT EXISTS campus_content (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL, title TEXT NOT NULL, details TEXT, media BLOB, media_type TEXT, media_name TEXT, created_on TEXT NOT NULL DEFAULT CURRENT_DATE)")
        conn.execute("CREATE TABLE IF NOT EXISTS placement_companies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, visit_year TEXT, notes TEXT, logo BLOB, logo_type TEXT, logo_name TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS college_events (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, event_date TEXT NOT NULL, details TEXT, category TEXT NOT NULL DEFAULT 'Event')")
        conn.execute("CREATE TABLE IF NOT EXISTS assignment_submissions (id INTEGER PRIMARY KEY AUTOINCREMENT, assignment_id INTEGER NOT NULL, username TEXT NOT NULL, submitted_on TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, file_name TEXT NOT NULL, file_data BLOB NOT NULL, status TEXT NOT NULL DEFAULT 'Submitted', feedback TEXT, UNIQUE(assignment_id, username))")
        conn.commit()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

def password_matches(stored_password: str, candidate: str) -> bool:
    # New accounts use bcrypt. Existing demo accounts used plaintext; migrate them
    # to bcrypt after their first successful login, without losing the account.
    if stored_password.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(candidate.encode("utf-8"), stored_password.encode("utf-8"))
        except ValueError:
            return False
    return hmac.compare_digest(stored_password, candidate)

def verify_login(username: str, password: str):
    username = username.strip()
    with db_connect() as conn:
        row = conn.execute(
            "SELECT username, password, name, role, active FROM students WHERE username = ?",
            (username,)
        ).fetchone()
        if not row or not row["active"] or not password_matches(row["password"], password):
            return None
        if not row["password"].startswith(("$2a$", "$2b$", "$2y$")):
            conn.execute(
                "UPDATE students SET password = ? WHERE username = ?",
                (hash_password(password), username)
            )
        return {"username": row["username"], "name": row["name"], "role": row["role"] or "student"}

def register_student(name, username, email, password, course):
    name, username, email = name.strip(), username.strip(), email.strip().lower()
    if not all([name, username, email, password, course]):
        return False, "Please complete every field."
    if len(username) < 3 or not username.replace("_", "").replace("-", "").isalnum():
        return False, "Username must be at least 3 characters and use letters, numbers, _ or -."
    if len(password) < 10:
        return False, "Use a password with at least 10 characters."
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return False, "Enter a valid email address."
    with db_connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM students WHERE lower(username)=lower(?) OR lower(email)=lower(?)",
            (username, email)
        ).fetchone()
        if exists:
            return False, "That username or email is already registered."
        conn.execute(
            """INSERT INTO students (username, password, name, fee_status, course, email, role)
               VALUES (?, ?, ?, ?, ?, ?, 'student')""",
            (username, hash_password(password), name, "Unknown", course, email)
        )
        conn.commit()
    return True, "Account created. You can now log in."

def get_student_data(username):
    with db_connect() as conn:
        row = conn.execute(
            "SELECT name, fee_status, course, email, profile_picture FROM students WHERE username = ?",
            (username,)
        ).fetchone()
    if row:
        return {"name": row["name"], "fee_status": row["fee_status"], "course": row["course"],
                "email": row["email"], "profile_picture": row["profile_picture"]}
    return None

def get_course_timetable(course):
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT day, schedule FROM timetables WHERE course = ?",
            (course,)
        ).fetchall()
    return {row["day"]: row["schedule"] for row in rows}

def bootstrap_admin_from_environment():
    """Create the configured administrator from Streamlit Secrets or local .env.

    The configured password is synchronized to this designated admin account so
    a stale local SQLite password cannot block the deployed administrator login.
    """
    username = get_config("ADMIN_USERNAME").strip()
    password = get_config("ADMIN_PASSWORD")
    if not username or not password:
        return

    with db_connect() as conn:
        row = conn.execute(
            "SELECT username FROM students WHERE lower(username)=lower(?)",
            (username,)
        ).fetchone()

        if row:
            conn.execute(
                "UPDATE students SET password=?, name=?, role='admin', active=1 "
                "WHERE lower(username)=lower(?)",
                (hash_password(password), "College Administrator", username)
            )
        else:
            conn.execute(
                """INSERT INTO students
                   (username, password, name, fee_status, course, email, role, active)
                   VALUES (?, ?, ?, 'N/A', 'Administrator', NULL, 'admin', 1)""",
                (username, hash_password(password), "College Administrator")
            )
        conn.commit()

init_database()
bootstrap_admin_from_environment()

# Seed only empty public-information fields from the official GNIOT website.
# Admin edits are never overwritten on subsequent app launches.
OFFICIAL_PUBLIC_INFO = {
    "about": ("About the college", "Greater Noida Institute of Technology (GNIOT) is an engineering and management institution in Knowledge Park II, Greater Noida. The official website states that the institute was established in 2001 by Shri Ram Educational Trust, Noida, on a not-for-profit basis. It is approved by AICTE and affiliated with Dr. A.P.J. Abdul Kalam Technical University (AKTU), Lucknow."),
    "mission": ("Our mission", "• Build a multidisciplinary engineering education ecosystem that transforms learners into innovators, entrepreneurs, and professional leaders.\n\n• Encourage interdisciplinary research, innovation, and creativity to address regional and global challenges.\n\n• Support critical and design thinking, life skills, and quality learning.\n\n• Collaborate with academic and industry partners to improve productivity and outcomes."),
    "vision": ("Our vision", "Be known globally for value-added education, innovation, and research at the intersection of disciplines in service of humankind."),
    "history": ("Founding and history", "The official GNIOT history page states that the institute was established in 2001 by Shri Ram Educational Trust, Noida. The Trust was formed in 2000. GNIOT is located in Knowledge Park II, Greater Noida, Uttar Pradesh. Please verify any individual founder attribution with the college before publishing it."),
}
with db_connect() as conn:
    for section, (title, content) in OFFICIAL_PUBLIC_INFO.items():
        existing = conn.execute("SELECT content FROM college_info WHERE section=?", (section,)).fetchone()
        if not existing:
            conn.execute("INSERT INTO college_info(section,title,content) VALUES(?,?,?)", (section, title, content))
        elif not (existing["content"] or "").strip():
            conn.execute("UPDATE college_info SET title=?, content=? WHERE section=?", (title, content, section))
    conn.commit()

# ---------------- Preserve the existing voice chatbot ----------------
def transcribe_audio(audio_bytes):
    """Transcribe microphone audio with Groq Whisper; no local FFmpeg required."""
    if not audio_bytes:
        return None
    try:
        # Streamlit mic recorder commonly returns WebM/Opus bytes. Groq accepts
        # the original media bytes directly, avoiding a local ffprobe dependency.
        audio_file = ("student_question.webm", audio_bytes)
        transcription = client.audio.transcriptions.create(
            file=audio_file,
            model=os.getenv("GROQ_AUDIO_MODEL", "whisper-large-v3-turbo"),
            response_format="text",
        )
        text = getattr(transcription, "text", transcription)
        text = str(text).strip()
        if text:
            return text
        st.warning("Could not understand the audio. Please try again.")
        return None
    except Exception as groq_error:
        # Keep a local fallback for WAV recordings where SpeechRecognition can
        # decode the audio without FFmpeg.
        try:
            recognizer = sr.Recognizer()
            with sr.AudioFile(BytesIO(audio_bytes)) as source:
                audio_data = recognizer.record(source)
            return recognizer.recognize_google(
                audio_data, language=st.session_state.selected_language_code
            )
        except Exception:
            st.error(
                "Voice transcription failed. You can still type your question. "
                f"Details: {groq_error}"
            )
            return None

def text_to_audio_autoplay(text, lang_code):
    """Generate a natural neural voice similar in style to a polished assistant voice."""
    try:
        import asyncio
        import edge_tts

        voice_map = {
            "en": "en-US-AriaNeural",
            "hi": "hi-IN-SwaraNeural",
            "fr": "fr-FR-DeniseNeural",
            "de": "de-DE-KatjaNeural",
            "es": "es-ES-ElviraNeural",
        }
        voice = voice_map.get((lang_code or "en").split("-")[0], "en-US-AriaNeural")

        async def synthesize():
            communicate = edge_tts.Communicate(text, voice)
            audio = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio.extend(chunk["data"])
            return bytes(audio)

        audio_bytes = asyncio.run(synthesize())
        if not audio_bytes:
            raise RuntimeError("The voice service returned no audio.")
        b64 = base64.b64encode(audio_bytes).decode()
        return f'<audio autoplay controls><source src="data:audio/mpeg;base64,{b64}" type="audio/mpeg"></audio>'
    except Exception as e:
        st.warning(f"Could not generate assistant voice. You can still read the response. Details: {e}")
        return None

def get_bot_response(user_query, language_name, language_code, student_data):
    faq_text = "\n".join(
        f"{q}: {a}" for q, a in zip(faq_df["question"], faq_df["answer"])
    )
    timetable = get_course_timetable(student_data["course"])
    timetable_text = "\n".join(f"{day}: {schedule}" for day, schedule in timetable.items())
    system_instruction = f"""
You are a helpful and polite college chatbot assistant for Greater Noida Institute of Technology (GNIT).

Student Info:
- Name: {student_data['name']}
- Fee Status: {student_data['fee_status']}
- Course: {student_data['course']}

General FAQs:
{faq_text}

Student Timetable:
{timetable_text}

CRITICAL RULES:
1. The user's preferred language is {language_name}.
2. Understand the user's query regardless of the language.
3. Reply ONLY in {language_name}.
4. Keep answers concise.
5. Do not provide information about other students.
6. Do not invent official college information; if the answer is not in the provided information, say it is not available yet.
7. If the user asks for full timetable, reply that they can see it via the Timetable button.
"""
    try:
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_query},
        ]
        configured_model = os.getenv("GROQ_MODEL", "").strip()
        model_candidates = []
        for candidate in [configured_model, "openai/gpt-oss-120b", "llama-3.1-8b-instant"]:
            if candidate and candidate not in model_candidates:
                model_candidates.append(candidate)
        last_error = None
        for model_name in model_candidates:
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=700,
                )
                return (response.choices[0].message.content or "").strip() or "I couldn't generate a response. Please try rephrasing your question."
            except Exception as model_error:
                last_error = model_error
                error_lower = str(model_error).lower()
                # Retry only for unavailable model IDs; don't mask auth, quota, or network errors.
                if any(token in error_lower for token in ["model_not_found", "does not exist", "decommissioned", "model is not available"]):
                    continue
                raise
        raise last_error
    except Exception as e:
        error_text = str(e)
        if "401" in error_text or "403" in error_text or "authentication" in error_text.lower():
            return "Groq rejected the API key. Check GROQ_API_KEY in your .env file. Never share your key in chat."
        if "model" in error_text.lower() and ("not found" in error_text.lower() or "decommission" in error_text.lower()):
            return "The configured Groq model is unavailable. Check GROQ_MODEL in your .env file."
        return f"I couldn't reach the AI service just now. Please try again. (Details: {error_text[:180]})"

# ---------------- Session state ----------------
defaults = {
    "logged_in": False, "username": None, "student_name": None, "user_role": None,
    "messages": [], "last_prompt": None, "selected_language_name": "English",
    "selected_language_code": "en", "voice_input": None, "show_timetable": False,
    "language_changed": False, "active_section": "AI Help Desk"
}
for key, default in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default

def logout():
    for key in defaults:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# ---------------- Login and registration screens ----------------
if not st.session_state.logged_in:
    st.markdown('<div class="portal-brand">Greater Noida Institute of Technology</div>', unsafe_allow_html=True)
    st.title("College Help Desk")
    st.markdown("Access academic services, verified campus information, and student support from one place.")

    with st.container(border=True):
        st.markdown("#### Sign in or request access")
        auth_mode = st.radio("Choose your portal", ["Student", "Teacher / Faculty", "Administrator"], horizontal=True, key="auth_mode", label_visibility="collapsed")
        if auth_mode == "Student":
            login_tab, register_tab = st.tabs(["Student login", "Register as a student"])
            with login_tab:
                with st.form("login_form", border=False):
                    login_username = st.text_input("Username", key="login_username", placeholder="Enter your username")
                    login_password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
                    login_submit = st.form_submit_button("Sign in to student portal", use_container_width=True, type="primary")
                if login_submit:
                    user = verify_login(login_username, login_password)
                    if user and user["role"] == "student":
                        st.session_state.logged_in=True; st.session_state.username=user["username"]; st.session_state.student_name=user["name"]; st.session_state.user_role=user["role"]; st.session_state.messages=[]; st.rerun()
                    elif user:
                        st.error("This account belongs to a different portal. Choose the matching portal above.")
                    else: st.error("We couldn't sign you in. Check your username and password.")
            with register_tab:
                with st.form("register_form", clear_on_submit=False, border=False):
                    new_name=st.text_input("Full name", placeholder="As shown on your college records")
                    new_username=st.text_input("Choose a username", placeholder="At least 3 characters")
                    new_email=st.text_input("College or personal email", placeholder="you@example.com")
                    new_course=st.selectbox("Course / programme", ["B.Tech CSE", "B.Tech IT", "B.Tech ECE", "B.Tech Mechanical", "MBA", "MCA", "Other"])
                    new_password=st.text_input("Create password", type="password", help="Use at least 10 characters.")
                    confirm_password=st.text_input("Confirm password", type="password")
                    register_submit=st.form_submit_button("Create student account", use_container_width=True, type="primary")
                if register_submit:
                    if new_password != confirm_password: st.error("Passwords do not match.")
                    else:
                        ok,message=register_student(new_name,new_username,new_email,new_password,new_course)
                        (st.success if ok else st.error)(message)
                        if ok: st.info("Your account is ready. Open Student login to sign in.")
        elif auth_mode == "Teacher / Faculty":
            st.caption("Faculty access is reviewed by the college administrator. Requests do not grant access automatically.")
            request_tab, faculty_login_tab = st.tabs(["Request faculty access", "Faculty login"])
            with request_tab:
                with st.form("faculty_request_form", clear_on_submit=True):
                    fac_name=st.text_input("Full name")
                    fac_username=st.text_input("Choose username")
                    fac_email=st.text_input("Official / college email")
                    fac_department=st.selectbox("Department", ["Computer Science & Engineering", "Information Technology", "Electronics & Communication", "Mechanical Engineering", "Management", "Applied Sciences", "Administration", "Other"])
                    fac_designation=st.text_input("Designation", placeholder="e.g. Assistant Professor")
                    fac_password=st.text_input("Create password", type="password", help="Use at least 10 characters.")
                    fac_confirm=st.text_input("Confirm password", type="password")
                    fac_submit=st.form_submit_button("Submit faculty access request", use_container_width=True, type="primary")
                if fac_submit:
                    if not all([fac_name.strip(),fac_username.strip(),fac_email.strip(),fac_department,fac_designation.strip()]): st.error("Please complete every field.")
                    elif len(fac_username.strip())<3: st.error("Username must contain at least 3 characters.")
                    elif len(fac_password)<10: st.error("Password must contain at least 10 characters.")
                    elif fac_password != fac_confirm: st.error("Passwords do not match.")
                    else:
                        try:
                            with db_connect() as conn:
                                existing=conn.execute("SELECT username FROM students WHERE lower(username)=lower(?) UNION SELECT username FROM faculty_access_requests WHERE lower(username)=lower(?)",(fac_username.strip(),fac_username.strip())).fetchone()
                                if existing: st.error("That username is already in use. Choose another.")
                                else:
                                    conn.execute("INSERT INTO faculty_access_requests(full_name,username,email,department,designation,password_hash) VALUES(?,?,?,?,?,?)",(fac_name.strip(),fac_username.strip(),fac_email.strip(),fac_department,fac_designation.strip(),hash_password(fac_password)))
                                    conn.commit(); st.success("Request submitted. The administrator must approve it before faculty access is enabled.")
                        except sqlite3.IntegrityError: st.error("A request already exists for this username.")
            with faculty_login_tab:
                st.info("Faculty sign-in will be enabled after your request is approved. If already approved, use the credentials confirmed by the administrator.")
                with st.form("faculty_login_form"):
                    faculty_login_username=st.text_input("Faculty username", key="faculty_login_username")
                    faculty_login_password=st.text_input("Password", type="password", key="faculty_login_password")
                    faculty_login_submit=st.form_submit_button("Faculty sign-in", use_container_width=True, type="primary")
                if faculty_login_submit:
                    user=verify_login(faculty_login_username,faculty_login_password)
                    if user and user["role"] == "faculty":
                        st.session_state.logged_in=True; st.session_state.username=user["username"]; st.session_state.student_name=user["name"]; st.session_state.user_role="faculty"; st.session_state.messages=[]; st.rerun()
                    elif user: st.error("This account does not have approved faculty access.")
                    else: st.error("Sign-in failed. Check your credentials or wait for administrator approval.")
        else:
            st.caption("Restricted area for the designated administrator. Access is verified against the configured admin account.")
            with st.form("admin_login_form"):
                admin_username=st.text_input("Administrator username", key="admin_login_username")
                admin_password=st.text_input("Administrator password", type="password", key="admin_login_password")
                admin_submit=st.form_submit_button("Administrator sign in", use_container_width=True, type="primary")
            if admin_submit:
                user=verify_login(admin_username,admin_password)
                if user and user["role"] == "admin":
                    st.session_state.logged_in=True; st.session_state.username=user["username"]; st.session_state.student_name=user["name"]; st.session_state.user_role="admin"; st.session_state.messages=[]; st.rerun()
                else: st.error("Administrator sign-in failed. Use the configured administrator account.")

    st.markdown("### College information")
    with db_connect() as conn:
        public_info={r["section"]:dict(r) for r in conn.execute("SELECT section,title,content FROM college_info WHERE section IN ('about','mission','vision','history')").fetchall()}
    info_tabs=st.tabs(["About us", "Mission", "Vision", "History"])
    info_defaults={"about":("About the college","College overview will be published by the administrator."),"mission":("Our mission","The official mission statement will be published by the administrator."),"vision":("Our vision","The official vision statement will be published by the administrator."),"history":("History and founding","Verified founding details will be published by the administrator.")}
    for tab,key in zip(info_tabs,["about","mission","vision","history"]):
        with tab:
            info=public_info.get(key,{})
            st.markdown("#### "+info.get("title",info_defaults[key][0]))
            st.markdown('<div class="public-info-scroll">'+(info.get("content") or info_defaults[key][1]).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\n","<br><br>")+'</div>',unsafe_allow_html=True)

    with st.expander("Frequently asked questions", expanded=False):
        if {"question","answer"}.issubset(set(faq_df.columns)):
            for _,faq_row in faq_df.fillna("").iterrows():
                with st.expander(str(faq_row["question"])): st.write(str(faq_row["answer"]))
        else: st.info("FAQs are unavailable because faqs.csv must contain 'question' and 'answer' columns.")
    with st.expander("Forgot your password?", expanded=False):
        st.write("Submit a password-reset request. The administrator will verify your account before taking action.")
        with st.form("forgot_password_form", clear_on_submit=True):
            reset_identity=st.text_input("Username or registered email")
            reset_submit=st.form_submit_button("Request password reset")
        if reset_submit:
            identity=reset_identity.strip()
            if identity:
                with db_connect() as conn:
                    found=conn.execute("SELECT username,email FROM students WHERE (lower(username)=lower(?) OR lower(email)=lower(?)) AND role != 'admin'",(identity,identity)).fetchone()
                    if found:
                        pending=conn.execute("SELECT id FROM password_reset_requests WHERE username=? AND status='Pending'",(found["username"],)).fetchone()
                        if not pending: conn.execute("INSERT INTO password_reset_requests(username,email) VALUES(?,?)",(found["username"],found["email"]))
                        conn.commit()
                st.success("If the details match an account, a reset request has been recorded.")
            else: st.warning("Enter your username or registered email.")
    st.stop()

# Verify role from database on every app rerun, rather than trusting only session state.
with db_connect() as conn:
    current_user = conn.execute(
        "SELECT username, name, role, active FROM students WHERE username = ?",
        (st.session_state.username,)
    ).fetchone()
if not current_user or not current_user["active"]:
    logout()
st.session_state.user_role = current_user["role"] or "student"
st.session_state.student_name = current_user["name"]

if st.session_state.user_role == "admin":
    with st.sidebar:
        st.markdown(f"**Signed in:** {st.session_state.student_name}")
        st.caption("Role: Administrator")
        st.divider()
        if st.button("🚪 Log out", use_container_width=True, key="admin_logout"):
            logout()
    st.title("🛠️ GNIT Administrator Dashboard")
    with db_connect() as conn:
        student_count = conn.execute("SELECT COUNT(*) AS n FROM students WHERE role='student'").fetchone()["n"]
        timetable_count = conn.execute("SELECT COUNT(*) AS n FROM timetables").fetchone()["n"]
        faculty_count = conn.execute("SELECT COUNT(*) AS n FROM faculty").fetchone()["n"]
        book_count = conn.execute("SELECT COUNT(*) AS n FROM library_books").fetchone()["n"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Students", student_count); c2.metric("Timetable rows", timetable_count)
    c3.metric("Faculty", faculty_count); c4.metric("Book titles", book_count)
    st.caption("Changes saved here appear in the student portal. Enter only verified college information.")
    admin_tabs = st.tabs(["Students & security", "Faculty access requests", "Password resets", "Attendance", "Assignments", "Student queries", "Timetable", "Faculty", "Holidays", "Library", "Campus locations", "Announcements", "Fees & student summary", "College information", "Placements", "Campus life & events", "Assignment submissions"])

    with admin_tabs[0]:
        st.subheader("Student accounts & access control")
        with db_connect() as conn:
            students = [dict(r) for r in conn.execute("SELECT username,name,email,course,role,active FROM students ORDER BY name").fetchall()]
        if students:
            st.dataframe(students, use_container_width=True, hide_index=True)
            eligible = [r for r in students if r["role"] != "admin"]
            if eligible:
                chosen = st.selectbox("Choose student account", eligible, format_func=lambda r: f"{r['name']} (@{r['username']})", key="security_student")
                new_status = st.selectbox("Account status", ["Active", "Suspended"], index=0 if chosen["active"] else 1, key="security_status")
                if st.button("Save account status"):
                    with db_connect() as conn:
                        conn.execute("UPDATE students SET active=? WHERE username=?", (1 if new_status == "Active" else 0, chosen["username"]))
                        conn.commit()
                    st.success("Account access updated."); st.rerun()
        st.warning("Only suspend accounts when authorized. This does not delete student records.")

    with admin_tabs[1]:
        st.subheader("Teacher / faculty access requests")
        with db_connect() as conn:
            requests=[dict(r) for r in conn.execute("SELECT id,full_name,username,email,department,designation,status,created_on FROM faculty_access_requests ORDER BY created_on DESC").fetchall()]
        if not requests:
            st.info("No faculty access requests have been submitted yet.")
        else:
            st.dataframe(requests,use_container_width=True,hide_index=True)
            pending=[r for r in requests if r["status"]=="Pending"]
            if pending:
                chosen_request=st.selectbox("Choose a pending request",pending,format_func=lambda r:f"{r['full_name']} · {r['department']} · @{r['username']}",key="faculty_request_choice")
                review_note=st.text_input("Optional review note",key="faculty_review_note")
                approve_col,reject_col=st.columns(2)
                with approve_col:
                    if st.button("Approve faculty request",type="primary",use_container_width=True):
                        with db_connect() as conn:
                            conn.execute("INSERT INTO students(username,password,name,fee_status,course,email,role,active) VALUES(?,?,?,'N/A',?,?, 'faculty',1)",(chosen_request["username"],conn.execute("SELECT password_hash FROM faculty_access_requests WHERE id=?",(chosen_request["id"],)).fetchone()[0],chosen_request["full_name"],chosen_request["department"],chosen_request["email"]))
                            conn.execute("INSERT INTO faculty(name,department,designation,email) VALUES(?,?,?,?) ON CONFLICT DO NOTHING",(chosen_request["full_name"],chosen_request["department"],chosen_request["designation"],chosen_request["email"]))
                            conn.execute("UPDATE faculty_access_requests SET status='Approved',reviewed_on=CURRENT_TIMESTAMP WHERE id=?",(chosen_request["id"],)); conn.commit()
                        st.success("Faculty request approved. Note: faculty workspace features will be added in the next implementation step."); st.rerun()
                with reject_col:
                    if st.button("Reject request",use_container_width=True):
                        with db_connect() as conn: conn.execute("UPDATE faculty_access_requests SET status='Rejected',reviewed_on=CURRENT_TIMESTAMP WHERE id=?",(chosen_request["id"],)); conn.commit()
                        st.success("Request rejected."); st.rerun()

    with admin_tabs[2]:
        st.subheader("Password reset requests")
        st.caption("Verify the student's identity before issuing a temporary password. Share it only through an approved private channel.")
        with db_connect() as conn:
            reset_rows = [dict(r) for r in conn.execute("SELECT pr.*, s.name FROM password_reset_requests pr LEFT JOIN students s ON s.username=pr.username ORDER BY CASE pr.status WHEN 'Pending' THEN 0 ELSE 1 END, pr.created_on DESC").fetchall()]
        if not reset_rows:
            st.info("There are no password reset requests.")
        else:
            st.dataframe(reset_rows, use_container_width=True, hide_index=True)
            pending_resets = [r for r in reset_rows if r["status"] == "Pending"]
            if pending_resets:
                reset_choice = st.selectbox("Select a pending request", pending_resets, format_func=lambda r: f"{r.get('name') or r['username']} (@{r['username']}) — request #{r['id']}", key="pending_reset_choice")
                if st.button("Generate temporary password", type="primary", key="generate_temp_password"):
                    temporary_password = secrets.token_urlsafe(9)
                    with db_connect() as conn:
                        conn.execute("UPDATE students SET password=? WHERE username=? AND role != 'admin'", (hash_password(temporary_password), reset_choice["username"]))
                        conn.execute("UPDATE password_reset_requests SET status='Resolved', resolved_on=CURRENT_TIMESTAMP WHERE id=?", (reset_choice["id"],))
                        conn.commit()
                    st.session_state["issued_temp_password"] = temporary_password
                    st.session_state["issued_temp_username"] = reset_choice["username"]
                    st.success("Temporary password generated. Share it privately after verifying the student's identity.")
            if st.session_state.get("issued_temp_password"):
                st.warning(f"Temporary password for @{st.session_state.get('issued_temp_username')}: {st.session_state['issued_temp_password']} — copy it now and share privately. It will remain visible to this admin session until you clear it.")
                if st.button("Clear displayed temporary password", key="clear_temp_password"):
                    st.session_state.pop("issued_temp_password", None)
                    st.session_state.pop("issued_temp_username", None)
                    st.rerun()

    with admin_tabs[3]:
        st.subheader("Record attendance")
        with db_connect() as conn:
            students = [dict(r) for r in conn.execute("SELECT username,name,course FROM students WHERE role='student' AND active=1 ORDER BY name").fetchall()]
        if students:
            with st.form("attendance_form"):
                who = st.selectbox("Student", students, format_func=lambda r: f"{r['name']} — {r['course']} (@{r['username']})")
                attendance_date = st.date_input("Class date")
                attendance_status = st.selectbox("Status", ["Present", "Absent", "Late", "Excused"])
                attendance_notes = st.text_input("Notes (optional)")
                if st.form_submit_button("Save attendance"):
                    with db_connect() as conn:
                        conn.execute("INSERT INTO attendance(username,class_date,course,status,notes) VALUES(?,?,?,?,?) ON CONFLICT(username,class_date,course) DO UPDATE SET status=excluded.status, notes=excluded.notes", (who["username"], attendance_date.isoformat(), who["course"], attendance_status, attendance_notes.strip()))
                        conn.commit()
                    st.success("Attendance saved."); st.rerun()
        else: st.info("No active student accounts found.")
        with db_connect() as conn: attendance_rows = conn.execute("SELECT a.class_date,s.name,a.course,a.status,a.notes FROM attendance a JOIN students s ON s.username=a.username ORDER BY a.class_date DESC LIMIT 300").fetchall()
        if attendance_rows: st.dataframe([dict(r) for r in attendance_rows], use_container_width=True, hide_index=True)

    with admin_tabs[4]:
        st.subheader("Assignments & deadlines")
        with db_connect() as conn: assignment_rows = conn.execute("SELECT * FROM assignments ORDER BY due_date").fetchall()
        if assignment_rows: st.dataframe([dict(r) for r in assignment_rows], use_container_width=True, hide_index=True)
        with st.form("add_assignment"):
            acourse = st.selectbox("Course for assignment", ["All courses", "B.Tech CSE", "B.Tech IT", "B.Tech ECE", "B.Tech Mechanical", "MBA", "MCA", "Other"])
            atitle = st.text_input("Assignment title")
            adetails = st.text_area("Instructions")
            adue = st.date_input("Due date")
            if st.form_submit_button("Publish assignment"):
                if atitle.strip():
                    with db_connect() as conn: conn.execute("INSERT INTO assignments(course,title,details,due_date) VALUES(?,?,?,?)", (acourse,atitle.strip(),adetails.strip(),adue.isoformat())); conn.commit()
                    st.success("Assignment published."); st.rerun()
                else: st.error("Assignment title is required.")
        if assignment_rows:
            aid = st.selectbox("Assignment ID to delete", ["None"]+[str(r["id"]) for r in assignment_rows])
            if st.button("Delete assignment") and aid != "None":
                with db_connect() as conn: conn.execute("DELETE FROM assignments WHERE id=?",(int(aid),)); conn.commit()
                st.success("Assignment deleted."); st.rerun()

    with admin_tabs[5]:
        st.subheader("Student queries & complaints")
        with db_connect() as conn: query_rows = conn.execute("SELECT q.*,s.name FROM student_queries q LEFT JOIN students s ON s.username=q.username ORDER BY CASE q.status WHEN 'Open' THEN 0 WHEN 'In progress' THEN 1 ELSE 2 END, q.created_on DESC").fetchall()
        if query_rows:
            for q in query_rows:
                with st.container(border=True):
                    st.markdown(f"**#{q['id']} · {q['subject']}** — {q['name']} (@{q['username']})")
                    st.caption(f"{q['category']} · {q['created_on']} · Status: {q['status']}")
                    st.write(q['details'])
                    if q['admin_response']: st.info("Response: " + q['admin_response'])
                    with st.form(f"respond_query_{q['id']}"):
                        qstatus = st.selectbox("Update status", ["Open", "In progress", "Resolved"], index=["Open", "In progress", "Resolved"].index(q['status']) if q['status'] in ["Open", "In progress", "Resolved"] else 0, key=f"qstatus_{q['id']}")
                        qresponse = st.text_area("Reply to student", value=q['admin_response'] or "", key=f"qresponse_{q['id']}")
                        if st.form_submit_button("Save response"):
                            with db_connect() as conn: conn.execute("UPDATE student_queries SET status=?,admin_response=?,updated_on=CURRENT_TIMESTAMP WHERE id=?",(qstatus,qresponse.strip(),q['id'])); conn.commit()
                            st.success("Response saved."); st.rerun()
        else: st.info("No student queries submitted yet.")

    with admin_tabs[6]:
        st.subheader("Manage course timetable")
        with db_connect() as conn:
            timetable_rows = conn.execute("SELECT id, course, day, schedule FROM timetables ORDER BY course, id").fetchall()
        if timetable_rows:
            st.dataframe([dict(r) for r in timetable_rows], use_container_width=True, hide_index=True)
            delete_id = st.selectbox("Delete timetable row ID", ["None"] + [str(r["id"]) for r in timetable_rows])
            if st.button("Delete selected timetable row") and delete_id != "None":
                with db_connect() as conn: conn.execute("DELETE FROM timetables WHERE id=?", (int(delete_id),)); conn.commit()
                st.success("Timetable row deleted."); st.rerun()
        with st.form("add_timetable"):
            course = st.selectbox("Course", sorted(set(["B.Tech CSE", "B.Tech IT", "B.Tech ECE", "B.Tech Mechanical", "MBA", "MCA"] + [r["course"] for r in timetable_rows])))
            day = st.selectbox("Day", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
            schedule = st.text_area("Schedule", placeholder="09:00-10:00: Mathematics, 10:00-11:00: Physics")
            if st.form_submit_button("Add timetable row"):
                if schedule.strip():
                    with db_connect() as conn: conn.execute("INSERT INTO timetables(course, day, schedule) VALUES (?, ?, ?)", (course, day, schedule.strip())); conn.commit()
                    st.success("Timetable row added."); st.rerun()
                else: st.error("Enter a schedule.")

    with admin_tabs[7]:
        st.subheader("Faculty directory")
        with db_connect() as conn: rows = conn.execute("SELECT * FROM faculty ORDER BY name").fetchall()
        if rows: st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
        with st.form("add_faculty"):
            name = st.text_input("Faculty name"); department = st.text_input("Department"); designation = st.text_input("Designation")
            email = st.text_input("Email"); phone = st.text_input("Phone"); office = st.text_input("Office / room")
            if st.form_submit_button("Add faculty"):
                if name.strip():
                    with db_connect() as conn: conn.execute("INSERT INTO faculty(name,department,designation,email,phone,office) VALUES(?,?,?,?,?,?)", (name.strip(),department.strip(),designation.strip(),email.strip(),phone.strip(),office.strip())); conn.commit()
                    st.success("Faculty added."); st.rerun()
                else: st.error("Faculty name is required.")
        if rows:
            faculty_delete = st.selectbox("Faculty ID to delete", ["None"] + [str(r["id"]) for r in rows])
            if st.button("Delete faculty") and faculty_delete != "None":
                with db_connect() as conn: conn.execute("DELETE FROM faculty WHERE id=?", (int(faculty_delete),)); conn.commit()
                st.success("Faculty removed."); st.rerun()

    with admin_tabs[8]:
        st.subheader("College holidays")
        with db_connect() as conn: rows = conn.execute("SELECT * FROM holidays ORDER BY date").fetchall()
        if rows: st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
        with st.form("add_holiday"):
            holiday_date = st.date_input("Date"); holiday_title = st.text_input("Holiday / event name"); holiday_details = st.text_area("Details")
            if st.form_submit_button("Add holiday"):
                if holiday_title.strip():
                    with db_connect() as conn: conn.execute("INSERT INTO holidays(date,title,details) VALUES(?,?,?)", (holiday_date.isoformat(),holiday_title.strip(),holiday_details.strip())); conn.commit()
                    st.success("Holiday added."); st.rerun()
                else: st.error("Enter a holiday name.")
        if rows:
            holiday_delete = st.selectbox("Holiday ID to delete", ["None"] + [str(r["id"]) for r in rows])
            if st.button("Delete holiday") and holiday_delete != "None":
                with db_connect() as conn: conn.execute("DELETE FROM holidays WHERE id=?", (int(holiday_delete),)); conn.commit()
                st.success("Holiday removed."); st.rerun()

    with admin_tabs[9]:
        st.subheader("Library inventory")
        with db_connect() as conn: rows = conn.execute("SELECT * FROM library_books ORDER BY title").fetchall()
        if rows: st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
        with st.form("add_book"):
            title = st.text_input("Book title"); author = st.text_input("Author"); book_course = st.text_input("Subject / course")
            total = st.number_input("Total copies", min_value=1, value=1, step=1); available = st.number_input("Available copies", min_value=0, value=1, step=1)
            if st.form_submit_button("Add book"):
                if title.strip() and available <= total:
                    with db_connect() as conn: conn.execute("INSERT INTO library_books(title,author,course,total_copies,available_copies) VALUES(?,?,?,?,?)", (title.strip(),author.strip(),book_course.strip(),int(total),int(available))); conn.commit()
                    st.success("Book added."); st.rerun()
                else: st.error("Enter a title and ensure available copies do not exceed total copies.")
        if rows:
            book_delete = st.selectbox("Book ID to delete", ["None"] + [str(r["id"]) for r in rows])
            if st.button("Delete book") and book_delete != "None":
                with db_connect() as conn: conn.execute("DELETE FROM library_books WHERE id=?", (int(book_delete),)); conn.commit()
                st.success("Book removed."); st.rerun()

    with admin_tabs[10]:
        st.subheader("Campus locations")
        with db_connect() as conn: rows = conn.execute("SELECT * FROM campus_locations ORDER BY name").fetchall()
        if rows: st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
        with st.form("add_location"):
            loc_name = st.text_input("Location name"); building = st.text_input("Building / block"); room = st.text_input("Room number")
            details = st.text_area("Directions / notes"); map_url = st.text_input("Map link (optional, URL)")
            if st.form_submit_button("Add location"):
                if loc_name.strip():
                    with db_connect() as conn: conn.execute("INSERT INTO campus_locations(name,building,room,details,map_url) VALUES(?,?,?,?,?)", (loc_name.strip(),building.strip(),room.strip(),details.strip(),map_url.strip())); conn.commit()
                    st.success("Location added."); st.rerun()
                else: st.error("Location name is required.")
        if rows:
            loc_delete = st.selectbox("Location ID to delete", ["None"] + [str(r["id"]) for r in rows])
            if st.button("Delete location") and loc_delete != "None":
                with db_connect() as conn: conn.execute("DELETE FROM campus_locations WHERE id=?", (int(loc_delete),)); conn.commit()
                st.success("Location removed."); st.rerun()

    with admin_tabs[11]:
        st.subheader("Announcements")
        with db_connect() as conn: rows = conn.execute("SELECT * FROM announcements ORDER BY posted_on DESC, id DESC").fetchall()
        if rows: st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
        with st.form("add_announcement"):
            ann_title = st.text_input("Announcement title"); ann_details = st.text_area("Announcement details")
            if st.form_submit_button("Publish announcement"):
                if ann_title.strip() and ann_details.strip():
                    with db_connect() as conn: conn.execute("INSERT INTO announcements(title,details) VALUES(?,?)", (ann_title.strip(),ann_details.strip())); conn.commit()
                    st.success("Announcement published."); st.rerun()
                else: st.error("Enter both title and details.")
        if rows:
            ann_delete = st.selectbox("Announcement ID to delete", ["None"] + [str(r["id"]) for r in rows])
            if st.button("Delete announcement") and ann_delete != "None":
                with db_connect() as conn: conn.execute("DELETE FROM announcements WHERE id=?", (int(ann_delete),)); conn.commit()
                st.success("Announcement removed."); st.rerun()
    with admin_tabs[12]:
        st.subheader("💳 Fees and student academic summary")
        with db_connect() as conn:
            fee_students = [dict(r) for r in conn.execute("SELECT username,name,email,course,fee_status FROM students WHERE role='student' ORDER BY name").fetchall()]
        if fee_students:
            st.dataframe(fee_students, use_container_width=True, hide_index=True)
            selected_fee = st.selectbox("Select student to update fee status", fee_students, format_func=lambda r: f"{r['name']} (@{r['username']})", key="fee_student_pick")
            fee_status = st.selectbox("Fee deposit status", ["Unknown", "Pending", "Partially paid", "Paid", "Overdue", "Scholarship / waiver"], index=["Unknown", "Pending", "Partially paid", "Paid", "Overdue", "Scholarship / waiver"].index(selected_fee["fee_status"] if selected_fee["fee_status"] in ["Unknown", "Pending", "Partially paid", "Paid", "Overdue", "Scholarship / waiver"] else "Unknown"), key="fee_status_pick")
            if st.button("Save fee status", type="primary"):
                with db_connect() as conn: conn.execute("UPDATE students SET fee_status=? WHERE username=?", (fee_status, selected_fee["username"])); conn.commit()
                st.success("Fee status updated."); st.rerun()
        with db_connect() as conn:
            summary = conn.execute("SELECT s.username,s.name,s.course,COUNT(a.id) AS classes,SUM(CASE WHEN a.status IN ('Present','Late') THEN 1 ELSE 0 END) AS attended FROM students s LEFT JOIN attendance a ON a.username=s.username WHERE s.role='student' GROUP BY s.username ORDER BY s.name").fetchall()
        st.markdown("#### Attendance percentage overview")
        summary_rows=[]
        for r in summary:
            total=r["classes"] or 0; attended=r["attended"] or 0
            summary_rows.append({"Student":r["name"],"Username":r["username"],"Course":r["course"],"Classes recorded":total,"Present / late":attended,"Attendance %":round(attended*100/total,1) if total else 0})
        st.dataframe(summary_rows, use_container_width=True, hide_index=True)

    with admin_tabs[13]:
        st.subheader("🏛️ Public college information")
        st.caption("Enter verified official information. These sections appear on the sign-in page.")
        with db_connect() as conn: current_info={r["section"]:dict(r) for r in conn.execute("SELECT * FROM college_info").fetchall()}
        for key, label in [("about","About the college"),("mission","Mission"),("vision","Vision"),("history","Founding and history")]:
            existing=current_info.get(key,{})
            with st.form("college_info_"+key):
                title=st.text_input(label+" heading", value=existing.get("title",label), key="info_title_"+key)
                content=st.text_area(label+" content", value=existing.get("content",""), height=110, key="info_content_"+key, placeholder="Enter verified official text...")
                if st.form_submit_button("Save "+label.lower()):
                    with db_connect() as conn: conn.execute("INSERT INTO college_info(section,title,content) VALUES(?,?,?) ON CONFLICT(section) DO UPDATE SET title=excluded.title,content=excluded.content",(key,title.strip() or label,content.strip())); conn.commit()
                    st.success(label+" saved."); st.rerun()

    with admin_tabs[14]:
        st.subheader("🎯 Placements and visiting companies")
        with db_connect() as conn: companies=[dict(r) for r in conn.execute("SELECT id,name,visit_year,notes,logo_type,logo_name FROM placement_companies ORDER BY visit_year DESC,name").fetchall()]
        if companies: st.dataframe(companies,use_container_width=True,hide_index=True)
        with st.form("add_placement_company"):
            company_name=st.text_input("Company name"); visit_year=st.text_input("Visit / placement year",placeholder="e.g. 2026"); company_notes=st.text_area("Role, drive details, or verified placement notes")
            company_logo=st.file_uploader("Company logo (optional)",type=["png","jpg","jpeg","webp"],key="company_logo_upload")
            if st.form_submit_button("Add company"):
                if company_name.strip():
                    logo_bytes=company_logo.getvalue() if company_logo else None
                    with db_connect() as conn: conn.execute("INSERT INTO placement_companies(name,visit_year,notes,logo,logo_type,logo_name) VALUES(?,?,?,?,?,?)",(company_name.strip(),visit_year.strip(),company_notes.strip(),logo_bytes,company_logo.type if company_logo else None,company_logo.name if company_logo else None)); conn.commit()
                    st.success("Company added."); st.rerun()
                else: st.error("Company name is required.")
        if companies:
            del_company=st.selectbox("Company record to remove",["None"]+[str(c["id"])+" — "+c["name"] for c in companies],key="del_company")
            if st.button("Delete company record") and del_company!="None":
                with db_connect() as conn: conn.execute("DELETE FROM placement_companies WHERE id=?",(int(del_company.split(" — ")[0]),)); conn.commit()
                st.success("Company removed."); st.rerun()

    with admin_tabs[15]:
        st.subheader("🏟️ Campus life, facilities, and upcoming events")
        category=st.selectbox("Content category",["Hostel facilities","Sports facilities","Grounds","Fests and celebrations","Campus facilities","Other"],key="campus_category")
        with st.form("campus_life_form"):
            content_title=st.text_input("Title",placeholder="e.g. Girls hostel facilities")
            content_details=st.text_area("Description / facilities / event details")
            media=st.file_uploader("Upload image or video (optional)",type=["png","jpg","jpeg","webp","mp4","mov"],key="campus_media_upload")
            if st.form_submit_button("Publish campus content"):
                if content_title.strip():
                    media_bytes=media.getvalue() if media else None
                    if media_bytes and len(media_bytes)>25*1024*1024: st.error("Media must be 25 MB or smaller.")
                    else:
                        with db_connect() as conn: conn.execute("INSERT INTO campus_content(category,title,details,media,media_type,media_name) VALUES(?,?,?,?,?,?)",(category,content_title.strip(),content_details.strip(),media_bytes,media.type if media else None,media.name if media else None)); conn.commit()
                        st.success("Campus content published."); st.rerun()
                else: st.error("Enter a title.")
        with db_connect() as conn: campus_rows=[dict(r) for r in conn.execute("SELECT id,category,title,details,media_type,media_name,created_on FROM campus_content ORDER BY id DESC").fetchall()]
        if campus_rows:
            st.dataframe(campus_rows,use_container_width=True,hide_index=True)
            del_campus=st.selectbox("Campus content to remove",["None"]+[str(r["id"])+" — "+r["title"] for r in campus_rows],key="del_campus")
            if st.button("Delete campus content") and del_campus!="None":
                with db_connect() as conn: conn.execute("DELETE FROM campus_content WHERE id=?",(int(del_campus.split(" — ")[0]),)); conn.commit()
                st.success("Campus content deleted."); st.rerun()
        st.markdown("#### Add an upcoming event")
        with st.form("upcoming_event_form"):
            event_title=st.text_input("Event name"); event_date=st.date_input("Event date"); event_category=st.selectbox("Event type",["Academic","Placement","Fest","Sports","Cultural","Holiday","Other"]); event_details=st.text_area("Event details")
            if st.form_submit_button("Publish event"):
                if event_title.strip():
                    with db_connect() as conn: conn.execute("INSERT INTO college_events(title,event_date,details,category) VALUES(?,?,?,?)",(event_title.strip(),event_date.isoformat(),event_details.strip(),event_category)); conn.commit()
                    st.success("Event published."); st.rerun()
                else: st.error("Enter an event name.")
        with db_connect() as conn: event_rows=[dict(r) for r in conn.execute("SELECT * FROM college_events ORDER BY event_date").fetchall()]
        if event_rows: st.dataframe(event_rows,use_container_width=True,hide_index=True)

    with admin_tabs[16]:
        st.subheader("📥 Assignment submissions")
        with db_connect() as conn:
            submissions=[dict(r) for r in conn.execute("SELECT sub.id,sub.assignment_id,sub.username,s.name,a.title,sub.submitted_on,sub.file_name,sub.status,sub.feedback FROM assignment_submissions sub JOIN students s ON s.username=sub.username JOIN assignments a ON a.id=sub.assignment_id ORDER BY sub.submitted_on DESC").fetchall()]
        if submissions:
            st.dataframe(submissions,use_container_width=True,hide_index=True)
            submission_choice=st.selectbox("Choose a submission",submissions,format_func=lambda r:f"#{r['id']} · {r['name']} · {r['title']}",key="submission_choice")
            with db_connect() as conn: file_row=conn.execute("SELECT file_name,file_data FROM assignment_submissions WHERE id=?",(submission_choice["id"],)).fetchone()
            if file_row: st.download_button("Download submitted assignment",data=file_row["file_data"],file_name=file_row["file_name"],key="download_submission")
            with st.form("submission_feedback_form"):
                sub_status=st.selectbox("Submission status",["Submitted","Reviewed","Needs changes","Accepted"],index=["Submitted","Reviewed","Needs changes","Accepted"].index(submission_choice["status"]),key="sub_status")
                sub_feedback=st.text_area("Feedback to student",value=submission_choice["feedback"] or "",key="sub_feedback")
                if st.form_submit_button("Save review"):
                    with db_connect() as conn: conn.execute("UPDATE assignment_submissions SET status=?,feedback=? WHERE id=?",(sub_status,sub_feedback.strip(),submission_choice["id"])); conn.commit()
                    st.success("Submission review saved."); st.rerun()
        else: st.info("No assignments have been submitted yet.")

    st.stop()

# ---------------- Faculty dashboard ----------------
if st.session_state.user_role == "faculty":
    with st.sidebar:
        st.markdown(f"**Signed in:** {st.session_state.student_name}")
        st.caption("Role: Approved faculty")
        if st.button("Log out", use_container_width=True, key="faculty_logout"):
            logout()
    st.title("Faculty workspace")
    st.caption("Publish academic updates and assignments for students. Use verified information only.")
    faculty_tabs=st.tabs(["Overview", "Publish announcement", "Create assignment", "Faculty directory"])
    with faculty_tabs[0]:
        with db_connect() as conn:
            announcement_count=conn.execute("SELECT COUNT(*) n FROM announcements").fetchone()["n"]
            assignment_count=conn.execute("SELECT COUNT(*) n FROM assignments").fetchone()["n"]
        a,b=st.columns(2); a.metric("Published announcements",announcement_count); b.metric("Assignments",assignment_count)
    with faculty_tabs[1]:
        with st.form("faculty_announcement_form",clear_on_submit=True):
            title=st.text_input("Announcement title")
            details=st.text_area("Announcement details")
            publish=st.form_submit_button("Publish announcement",type="primary")
        if publish:
            if title.strip() and details.strip():
                with db_connect() as conn: conn.execute("INSERT INTO announcements(title,details) VALUES(?,?)",(title.strip(),details.strip())); conn.commit()
                st.success("Announcement published."); st.rerun()
            else: st.error("Add a title and details.")
    with faculty_tabs[2]:
        with st.form("faculty_assignment_form",clear_on_submit=True):
            course=st.selectbox("Course",["B.Tech CSE","B.Tech IT","B.Tech ECE","B.Tech Mechanical","MBA","MCA","All courses"])
            title=st.text_input("Assignment title")
            details=st.text_area("Instructions")
            due_date=st.date_input("Due date")
            publish_assignment=st.form_submit_button("Create assignment",type="primary")
        if publish_assignment:
            if title.strip():
                with db_connect() as conn: conn.execute("INSERT INTO assignments(course,title,details,due_date) VALUES(?,?,?,?)",(course,title.strip(),details.strip(),due_date.isoformat())); conn.commit()
                st.success("Assignment created."); st.rerun()
            else: st.error("Enter an assignment title.")
    with faculty_tabs[3]:
        with db_connect() as conn: rows=[dict(r) for r in conn.execute("SELECT name,department,designation,email,phone,office FROM faculty ORDER BY department,name").fetchall()]
        if rows: st.dataframe(rows,use_container_width=True,hide_index=True)
        else: st.info("Faculty directory is not populated yet.")
    st.stop()

# ---------------- Student dashboard ----------------
st.title(f"🎓 Welcome {st.session_state.student_name}")
student_data = get_student_data(st.session_state.username)
if not student_data:
    st.error("Student data could not be found.")
    st.stop()

# Student services live in the sidebar beneath Controls. The main canvas opens directly to AI Help Desk.
if "active_section" not in st.session_state:
    st.session_state.active_section = "AI Help Desk"

nav_items = [
    ("My Profile", "👤"), ("AI Help Desk", "🤖"), ("Timetable", "🗓️"), ("Faculty", "👩‍🏫"),
    ("Holidays", "🎉"), ("Library", "📚"), ("Campus map & rooms", "📍"), ("Announcements", "📣"),
    ("Attendance", "📊"), ("Assignments", "📝"), ("Queries & complaints", "💬"), ("Account security", "🔐"),
    ("Placements", "🎯"), ("Campus life", "🏟️"), ("Upcoming events", "📅")
]
with st.sidebar:
    if student_data.get("profile_picture"):
        st.image(BytesIO(student_data["profile_picture"]), width=64)
    st.markdown(f'<div class="sidebar-user"><b>Signed in:</b> {student_data["name"]}<br><span style="color:#7a8190;font-size:.85rem">{student_data.get("course") or "Course not set"}</span></div>', unsafe_allow_html=True)

    # Prominent PagePilot launcher appears near the top of the student sidebar.
    st.markdown("""
    <style>
      .pagepilot-launch-card {
        position: relative;
        display: flex;
        align-items: center;
        gap: 14px;
        margin: 1.35rem 0 1.8rem;
        padding: 22px 18px;
        min-height: 116px;
        border-radius: 22px;
        color: #fff !important;
        text-decoration: none !important;
        background: linear-gradient(125deg, #9333ea 0%, #4f46e5 48%, #0284c7 100%);
        border: 1px solid rgba(255,255,255,.55);
        box-shadow: 0 10px 26px rgba(79,70,229,.22);
        transition: transform .18s ease, box-shadow .18s ease;
      }
      .pagepilot-launch-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 14px 30px rgba(79,70,229,.30);
      }
      .pagepilot-launch-icon {
        flex: 0 0 56px;
        width: 56px; height: 56px;
        display: grid; place-items: center;
        font-size: 32px;
        border-right: 1px solid rgba(255,255,255,.45);
        padding-right: 12px;
      }
      .pagepilot-launch-copy { flex: 1; min-width: 0; }
      .pagepilot-launch-title {
        font-size: 1.35rem; line-height: 1.2; font-weight: 800;
        margin-bottom: 7px; letter-spacing: -.02em;
      }
      .pagepilot-launch-subtitle {
        font-size: .92rem; line-height: 1.35; opacity: .96;
      }
      .pagepilot-launch-arrow {
        flex: 0 0 44px; width: 44px; height: 44px;
        border-radius: 50%; background: #fff; color: #4f46e5;
        display: grid; place-items: center; font-size: 25px; font-weight: 700;
      }
      .pagepilot-most-used {
        position: absolute; top: -13px; right: 12px;
        border-radius: 999px; padding: 5px 12px;
        color: #5b21b6; background: #fff;
        border: 1px solid #e9d5ff;
        box-shadow: 0 3px 10px rgba(0,0,0,.08);
        font-size: .75rem; font-weight: 800;
      }
      @media (max-width: 420px) {
        .pagepilot-launch-card { gap: 10px; padding: 18px 13px; }
        .pagepilot-launch-icon { flex-basis: 46px; width: 46px; font-size: 27px; }
        .pagepilot-launch-title { font-size: 1.15rem; }
        .pagepilot-launch-subtitle { font-size: .82rem; }
        .pagepilot-launch-arrow { flex-basis: 36px; width: 36px; height: 36px; }
      }
    </style>
    <a class="pagepilot-launch-card" href="https://pagepilot-ai.streamlit.app" target="_blank" rel="noopener noreferrer" aria-label="Open PagePilot AI Exam Prep and Study Hub">
      <span class="pagepilot-most-used">♛ Most Used</span>
      <span class="pagepilot-launch-icon">🎓</span>
      <span class="pagepilot-launch-copy">
        <span class="pagepilot-launch-title">PagePilot</span>
        <span class="pagepilot-launch-subtitle">AI Exam Prep &amp; Study Hub</span>
      </span>
      <span class="pagepilot-launch-arrow">→</span>
    </a>
    """, unsafe_allow_html=True)
    st.markdown("### ⚙️ Controls")
    languages = {
        "English": "en", "Hindi (हिन्दी)": "hi", "Punjabi (ਪੰਜਾਬੀ)": "pa",
        "Gujarati (ગુજરાતી)": "gu", "Marwari (मारवाड़ी)": "hi", "Marathi (मराठी)": "mr",
        "Bengali (বাংলা)": "bn", "Kannada (ಕನ್ನಡ)": "kn", "Tamil (தமிழ்)": "ta",
        "German (Deutsch)": "de", "French (Français)": "fr", "Spanish (Español)": "es", "Russian (Русский)": "ru",
    }
    language_names = list(languages.keys())
    if st.session_state.selected_language_name not in languages:
        st.session_state.selected_language_name = "English"
    selected_language_name = st.selectbox("Language", language_names, index=language_names.index(st.session_state.selected_language_name), key="global_language_select")
    if selected_language_name != st.session_state.selected_language_name:
        st.session_state.selected_language_name = selected_language_name
        st.session_state.selected_language_code = languages[selected_language_name]
        st.session_state.language_changed = True
    else:
        st.session_state.selected_language_code = languages[selected_language_name]
    st.markdown("##### 🎙️ Voice input")
    voice_input = mic_recorder(start_prompt="🎙️ Speak", stop_prompt="⏹️ Stop", key="voice_recorder_sidebar_global")
    if voice_input and voice_input.get("bytes"):
        st.session_state.voice_input = voice_input["bytes"]
    st.divider()
    st.markdown("### 🧭 Services")
    for start in range(0, len(nav_items), 2):
        cols = st.columns(2, gap="small")
        for col, (label, emoji) in zip(cols, nav_items[start:start+2]):
            with col:
                selected = st.session_state.active_section == label
                if st.button(f"{emoji} {label}", key=f"nav_{label}", use_container_width=True, type="primary" if selected else "secondary"):
                    st.session_state.active_section = label
                    st.rerun()

    st.divider()
    if st.button("🚪 Log out", use_container_width=True, key="student_logout"):
        logout()

active_section = st.session_state.active_section
if active_section == "AI Help Desk":
    st.markdown("<div class='portal-hero'><h2 style='margin:0'>🎓 GNIT Student Help Desk</h2><div class='portal-subtitle'>Ask a college-related question, use voice input, or choose a service from the sidebar.</div></div>", unsafe_allow_html=True)
if active_section == "My Profile":
    st.subheader("👤 My student profile")
    profile_left, profile_right = st.columns([1, 2], gap="large")
    with profile_left:
        with st.container(border=True):
            if student_data.get("profile_picture"):
                st.image(BytesIO(student_data["profile_picture"]), caption="Current profile picture", width=130)
            else:
                st.markdown("<div style='font-size:4rem;text-align:center;padding:1.0rem'>👤</div>", unsafe_allow_html=True)
                st.info("No profile picture yet")
            st.caption("JPG, PNG, or WEBP · Max 3 MB")
    with profile_right:
        with st.container(border=True):
            st.markdown("#### Student details")
            st.markdown(f"**Name:** {student_data['name']}")
            st.markdown(f"**Username:** {st.session_state.username}")
            st.markdown(f"**Email:** {student_data.get('email') or 'Not provided'}")
            st.markdown(f"**Course:** {student_data.get('course') or 'Not set'}")
            st.markdown(f"**Fee status:** {student_data.get('fee_status') or 'Not available'}")
        st.write("")
        st.markdown("#### Manage profile picture")
        uploaded_picture = st.file_uploader("Upload a new picture or choose a replacement", type=["png", "jpg", "jpeg", "webp"], help="Use a JPG, PNG, or WEBP image up to 3 MB.", key="profile_picture_upload")
        save_col, remove_col = st.columns(2)
        with save_col:
            if st.button("💾 Save profile picture", use_container_width=True, disabled=uploaded_picture is None):
                picture_bytes = uploaded_picture.getvalue() if uploaded_picture else b""
                if len(picture_bytes) > 3 * 1024 * 1024:
                    st.error("Please choose an image smaller than 3 MB.")
                elif picture_bytes:
                    try:
                        from PIL import Image
                        Image.open(BytesIO(picture_bytes)).verify()
                        with db_connect() as conn:
                            conn.execute("UPDATE students SET profile_picture=? WHERE username=?", (picture_bytes, st.session_state.username))
                            conn.commit()
                        st.success("Profile picture updated.")
                        st.rerun()
                    except Exception:
                        st.error("That image could not be opened. Please choose a valid JPG, PNG, or WEBP image.")
        with remove_col:
            if st.button("🗑️ Remove picture", use_container_width=True, disabled=not bool(student_data.get("profile_picture"))):
                with db_connect() as conn:
                    conn.execute("UPDATE students SET profile_picture=NULL WHERE username=?", (st.session_state.username,))
                    conn.commit()
                st.success("Profile picture removed.")
                st.rerun()
    st.caption("Your profile picture is stored with your student account and is visible when you sign in.")

if active_section == "AI Help Desk":
    st.caption(f"Course: {student_data['course']}  •  Fee status: {student_data['fee_status'] or 'Not available'}")


    chat_title_col, chat_clear_col = st.columns([5, 1])
    with chat_title_col:
        st.markdown("#### Ask the AI Help Desk")
    with chat_clear_col:
        if st.button("🗑️ Clear", key="chat_clear_current", help="Clear this conversation"):
            st.session_state.messages = []
            st.session_state.last_prompt = None
            st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = None
    if st.session_state.voice_input:
        prompt = transcribe_audio(st.session_state.voice_input)
        st.session_state.voice_input = None
    text_prompt = st.chat_input("Type your question here…")
    if text_prompt:
        prompt = text_prompt

    if prompt:
        if st.session_state.get("language_changed", False):
            st.session_state.language_changed = False
        elif st.session_state.get("last_prompt") != prompt:
            st.session_state.last_prompt = prompt
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Thinking…"):
                    reply = get_bot_response(
                        prompt, st.session_state.selected_language_name,
                        st.session_state.selected_language_code, student_data
                    )
                    st.markdown(reply)
                    audio_html = text_to_audio_autoplay(
                        reply, st.session_state.selected_language_code
                    )
                    if audio_html:
                        st.markdown(audio_html, unsafe_allow_html=True)
            st.session_state.messages.append({"role": "assistant", "content": reply})


if active_section == "Timetable":
    st.subheader("📅 Weekly timetable")
    timetable = get_course_timetable(student_data["course"])
    if timetable:
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        st.table(pd.DataFrame({"Day": days, "Schedule": [timetable.get(day, "Not published") for day in days]}))
    else:
        st.info("No timetable has been published for your course yet.")

if active_section == "Faculty":
    st.subheader("👩‍🏫 Faculty directory")
    with db_connect() as conn: rows = conn.execute("SELECT name, department, designation, email, phone, office FROM faculty ORDER BY department, name").fetchall()
    if rows: st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
    else: st.info("Faculty details have not been added yet. Please check with the college office.")

if active_section == "Holidays":
    st.subheader("🎉 Holidays and important dates")
    with db_connect() as conn: rows = conn.execute("SELECT date, title, details FROM holidays ORDER BY date").fetchall()
    if rows: st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
    else: st.info("No holidays have been published yet.")

if active_section == "Library":
    st.subheader("📚 Library book availability")
    search = st.text_input("Search by title, author, or course", key="library_search")
    with db_connect() as conn: rows = conn.execute("SELECT title, author, course, total_copies, available_copies FROM library_books ORDER BY title").fetchall()
    filtered = [dict(r) for r in rows if not search.strip() or search.lower() in " ".join(str(v or "") for v in r).lower()]
    if filtered: st.dataframe(filtered, use_container_width=True, hide_index=True)
    else: st.info("No matching book records found. Ask the library team to update the inventory.")

if active_section == "PagePilot Exam Prep":
    st.markdown("### 🧠 PagePilot Exam Prep")
    st.link_button("🚀 Launch PagePilot Exam Prep", "https://pagepilot-ai.streamlit.app",
                   use_container_width=True, type="primary")


if active_section == "Campus map & rooms":
    st.markdown("""
    <style>
    .campus-map-hero { padding: 1.6rem 1.8rem; border-radius: 20px;
        background: linear-gradient(135deg,#e8f0fe 0%,#f8faff 60%,#eaf4ff 100%);
        border: 1px solid #d6e4ff; margin-bottom: 1.25rem; }
    .campus-map-hero h2 { margin: 0 0 .4rem 0; color: #202124; }
    .campus-map-hero p { margin: 0; color: #5f6368; }
    .destination-card { border: 1px solid #dadce0; border-radius: 16px;
        padding: 1rem; background: #fff; min-height: 118px; }
    </style>
    <div class="campus-map-hero">
      <h2>📍 Find your way around GNIOT</h2>
      <p>Choose a campus landmark to open directions from your current location.</p>
    </div>
    """, unsafe_allow_html=True)
    destinations = [
        ("📚", "Library", "GNIOT College Library, Greater Noida"),
        ("🏫", "Girls' Hostel", "GNIOT Girls Hostel, Greater Noida"),
        ("🏫", "Boys' Hostel", "GNIOT Boys Hostel, Greater Noida"),
        ("🍽️", "Canteen", "GNIOT College Canteen, Greater Noida"),
        ("🏢", "Academic Block", "GNIOT Academic Block, Greater Noida"),
    ]
    import urllib.parse
    st.markdown("#### Campus destinations")
    st.caption("Select a destination below. Google Maps will open and use your device location when permission is enabled.")
    cols = st.columns(3, gap="medium")
    for i, (emoji, label, query) in enumerate(destinations):
        url = "https://www.google.com/maps/dir/?api=1&destination=" + urllib.parse.quote(query) + "&travelmode=walking"
        with cols[i % 3]:
            st.markdown(f"""
            <div class="destination-card">
              <div style="font-size:1.8rem;margin-bottom:.35rem">{emoji}</div>
              <div style="font-weight:650;color:#202124;font-size:1.05rem">{label}</div>
              <div style="color:#5f6368;font-size:.85rem;margin-top:.25rem">Walking directions</div>
            </div>
            """, unsafe_allow_html=True)
            st.link_button("Get directions →", url, use_container_width=True)
    st.info("For live directions, allow location access in your browser and make sure your device's location services are turned on.")
    with st.expander("Additional campus rooms", expanded=False):
        with db_connect() as conn:
            rows = conn.execute("SELECT name, building, room, details, map_url FROM campus_locations ORDER BY name").fetchall()
        if rows:
            for r in rows:
                with st.container(border=True):
                    st.markdown(f"**{r['name']}**")
                    details = " • ".join(str(v) for v in [r['building'], ('Room '+r['room']) if r['room'] else None] if v)
                    if details: st.write(details)
                    if r['details']: st.write(r['details'])
                    if r['map_url'] and str(r['map_url']).startswith(("https://","http://")):
                        st.link_button("Open directions", r['map_url'])
        else:
            st.caption("Additional room directions will appear here when published by the administrator.")

if active_section == "Announcements":
    st.subheader("📣 College announcements")
    with db_connect() as conn: rows = conn.execute("SELECT title, details, posted_on FROM announcements ORDER BY posted_on DESC, id DESC").fetchall()
    if rows:
        for r in rows:
            with st.container(border=True):
                st.markdown(f"**{r['title']}**")
                st.caption(r['posted_on'])
                st.write(r['details'])
    else: st.info("No announcements have been published yet.")


if active_section == "Attendance":
    st.subheader("📊 My attendance")
    with db_connect() as conn:
        rows = conn.execute("SELECT class_date,course,status,notes FROM attendance WHERE username=? ORDER BY class_date DESC", (st.session_state.username,)).fetchall()
    if rows:
        statuses = [r["status"] for r in rows]
        total = len(statuses); present = sum(1 for v in statuses if v in ("Present", "Late"))
        c1,c2,c3 = st.columns(3); c1.metric("Classes recorded", total); c2.metric("Present / late", present); c3.metric("Attendance rate", f"{present/total*100:.1f}%")
        st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
        st.caption("Rate is based only on attendance entries recorded in this portal.")
    else: st.info("Attendance has not been recorded for your account yet.")

if active_section == "Assignments":
    st.subheader("📝 Assignments & due dates")
    with db_connect() as conn:
        rows = conn.execute("SELECT id,title,details,due_date,course FROM assignments WHERE course IN (?, 'All courses') ORDER BY due_date", (student_data["course"],)).fetchall()
    if rows:
        for r in rows:
            with st.container(border=True):
                st.markdown(f"**{r['title']}**")
                st.caption(f"Course: {r['course']} · Due: {r['due_date']}")
                st.write(r['details'] or "No additional instructions provided.")
                with db_connect() as conn: existing=conn.execute("SELECT id,submitted_on,status,feedback,file_name FROM assignment_submissions WHERE assignment_id=? AND username=?",(r['id'],st.session_state.username)).fetchone()
                if existing:
                    st.success(f"Submitted on {existing['submitted_on']} · Status: {existing['status']} · File: {existing['file_name']}")
                    if existing['feedback']: st.info("Instructor feedback: "+existing['feedback'])
                with st.form(f"submit_assignment_{r['id']}"):
                    submission_file=st.file_uploader("Upload your assignment (PDF, DOCX, PPTX, ZIP, or image)",type=["pdf","docx","pptx","zip","png","jpg","jpeg"],key=f"assignment_file_{r['id']}")
                    submit_assignment=st.form_submit_button("Submit / replace assignment")
                if submit_assignment:
                    if not submission_file: st.warning("Choose a file first.")
                    elif len(submission_file.getvalue())>10*1024*1024: st.error("File must be 10 MB or smaller.")
                    else:
                        with db_connect() as conn: conn.execute("INSERT INTO assignment_submissions(assignment_id,username,file_name,file_data,status,feedback) VALUES(?,?,?,?, 'Submitted',NULL) ON CONFLICT(assignment_id,username) DO UPDATE SET submitted_on=CURRENT_TIMESTAMP,file_name=excluded.file_name,file_data=excluded.file_data,status='Submitted',feedback=NULL",(r['id'],st.session_state.username,submission_file.name,submission_file.getvalue())); conn.commit()
                        st.success("Assignment submitted."); st.rerun()
    else: st.info("No assignments have been published for your course yet.")

if active_section == "Placements":
    st.subheader("🎯 Placements and visiting companies")
    st.markdown(
        "Explore placement updates, recruiters, and career opportunities published by GNIOT."
    )
    st.link_button(
        "Visit the official GNIOT Placement website ↗",
        "https://www.gniotgroup.edu.in/placement.php",
        use_container_width=False,
    )
    with db_connect() as conn:
        companies=conn.execute("SELECT * FROM placement_companies ORDER BY visit_year DESC,name").fetchall()
    if companies:
        st.markdown("### Campus placement companies")
        for company in companies:
            with st.container(border=True):
                left,right=st.columns([1,4])
                with left:
                    if company["logo"]: st.image(BytesIO(company["logo"]),width=110)
                    else: st.markdown("<div style='font-size:2.5rem'>🏢</div>",unsafe_allow_html=True)
                with right:
                    st.markdown(f"**{company['name']}**")
                    if company["visit_year"]: st.caption("Visit / placement year: "+company["visit_year"])
                    if company["notes"]: st.write(company["notes"])
    else:
        st.info("Local placement company details will appear here when the administrator publishes them. Use the official placement website for current updates.")

if active_section == "Campus life":
    st.subheader("🏡 Hostel life at GNIOT")
    st.markdown(
        "Hostel life at the **Greater Noida Institute of Technology (GNIOT)** offers a "
        "**vibrant, structured, and closely-knit campus experience for outstation students "
        "coming from across India**."
    )
    st.markdown("### Accommodation and rooms")
    st.markdown(
        "- **On-campus living:** Separate residential blocks for boys and girls are located inside the campus, a short walk from the academic blocks.\n"
        "- **Room options:** Double- or triple-sharing, with occasional single rooms; AC, non-AC, and air-cooler options may be available.\n"
        "- **Furnishings:** Basic furniture includes a bed, mattress, study table, chair, cupboard, and bookshelf. Room amenities may vary.\n"
        "- **First-year students:** Dedicated wings or blocks may be used to support transition and student safety."
    )
    st.markdown("### Facilities and amenities")
    st.markdown(
        "- **Internet:** Wi-Fi and LAN connectivity in residential blocks.\n"
        "- **Food and mess:** Mess meals and on-campus cafeterias for snacks and refreshments.\n"
        "- **Recreation:** Common rooms, indoor games, gym, and nearby outdoor sports facilities.\n"
        "- **Utilities:** Power backup, drinking water, laundry/housekeeping, and hostel wardens."
    )
    st.caption("Hostel facilities, room types, and services can change. Confirm current availability and fees with the college.")
    st.markdown("### Explore the hostel and campus")
    gallery = [
        ("Common lounge", "campus_images/hostel_lounge.jpg"),
        ("Girls’ hostel exterior", "campus_images/girls_hostel.jpg"),
        ("Hostel room", "campus_images/hostel_room.jpg"),
        ("Dining hall", "campus_images/dining_hall.jpg"),
        ("Gym", "campus_images/gym.jpg"),
        ("Hostel courtyard", "campus_images/hostel_courtyard.jpg"),
        ("Boys’ hostel reception", "campus_images/boys_hostel_lobby.jpg"),
        ("Boys’ hostel entrance", "campus_images/boys_hostel_gate.jpg"),
        ("Outdoor sports court", "campus_images/sports_court.jpg"),
    ]
    cols = st.columns(3)
    for idx, (caption, relative_path) in enumerate(gallery):
        with cols[idx % 3]:
            image_path = BASE_DIR / relative_path
            if image_path.exists():
                st.image(str(image_path), caption=caption, use_container_width=True)
    st.markdown("### Official hostel information")
    st.link_button("View GNIOT hostel details ↗", "https://www.gniotgroup.edu.in/hostel.php")
    with db_connect() as conn:
        campus_rows=conn.execute("SELECT * FROM campus_content ORDER BY id DESC").fetchall()
    if campus_rows:
        st.markdown("### More campus updates")
        for item in campus_rows:
            with st.container(border=True):
                st.markdown(f"#### {item['title']}")
                st.caption(item["category"])
                if item["details"]: st.write(item["details"])
                if item["media"]:
                    if item["media_type"] and item["media_type"].startswith("video/"): st.video(item["media"])
                    elif item["media_type"] and item["media_type"].startswith("image/"): st.image(BytesIO(item["media"]),use_container_width=True)

if active_section == "Upcoming events":
    st.subheader("📅 Upcoming college events")
    with db_connect() as conn: events=conn.execute("SELECT title,event_date,category,details FROM college_events WHERE event_date >= date('now') ORDER BY event_date").fetchall()
    if events:
        for event in events:
            with st.container(border=True):
                st.markdown(f"#### {event['title']}")
                st.caption(f"{event['event_date']} · {event['category']}")
                if event["details"]: st.write(event["details"])
    else: st.info("No upcoming events have been published yet.")

if active_section == "Queries & complaints":
    st.subheader("💬 Submit a query or complaint")
    with st.form("student_query_form", clear_on_submit=True):
        category = st.selectbox("Category", ["Academic", "Attendance", "Fees", "Examination", "Faculty", "Facilities", "Technical issue", "Complaint", "Other"])
        subject = st.text_input("Subject")
        details = st.text_area("Describe your question or concern")
        submit_query = st.form_submit_button("Submit query")
    if submit_query:
        if subject.strip() and details.strip():
            with db_connect() as conn:
                conn.execute("INSERT INTO student_queries(username,category,subject,details) VALUES(?,?,?,?)", (st.session_state.username,category,subject.strip(),details.strip()))
                conn.commit()
            st.success("Your query was submitted. You can check its status below."); st.rerun()
        else: st.error("Please add a subject and details.")
    with db_connect() as conn:
        rows = conn.execute("SELECT category,subject,details,status,admin_response,created_on FROM student_queries WHERE username=? ORDER BY created_on DESC", (st.session_state.username,)).fetchall()
    st.markdown("#### My submissions")
    if rows:
        for r in rows:
            with st.container(border=True):
                st.markdown(f"**{r['subject']}**")
                st.caption(f"{r['category']} · Submitted {r['created_on']} · Status: {r['status']}")
                st.write(r['details'])
                if r['admin_response']: st.info("College response: " + r['admin_response'])
    else: st.info("You have not submitted any queries yet.")

if active_section == "Account security":
    st.subheader("🔐 Account security")
    st.write("Change your password regularly and never share it with anyone.")
    with st.form("change_password_form"):
        old_password = st.text_input("Current password", type="password")
        new_password = st.text_input("New password (10+ characters)", type="password")
        confirm_new_password = st.text_input("Confirm new password", type="password")
        change_password = st.form_submit_button("Change password")
    if change_password:
        with db_connect() as conn:
            row = conn.execute("SELECT password FROM students WHERE username=?", (st.session_state.username,)).fetchone()
            if not row or not password_matches(row["password"], old_password):
                st.error("Current password is incorrect.")
            elif len(new_password) < 10:
                st.error("New password must contain at least 10 characters.")
            elif new_password != confirm_new_password:
                st.error("New passwords do not match.")
            elif hmac.compare_digest(old_password, new_password):
                st.error("Choose a password different from your current password.")
            else:
                conn.execute("UPDATE students SET password=? WHERE username=?", (hash_password(new_password), st.session_state.username))
                conn.commit()
                st.success("Password changed successfully.")
