<<<<<<< HEAD

=======
from dotenv import load_dotenv
load_dotenv()

import os
import base64
import hmac
import secrets
import sqlite3
from io import BytesIO
from pathlib import Path

import streamlit as st
from google import genai
from google.genai import types
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
  .block-container {padding-top: 1.7rem; padding-bottom: 2.5rem; max-width: 1280px;}
  /* Prevent uploaded/profile images and form controls from overflowing their columns. */
  div[data-testid="stImage"] {max-width: 100%;}
  div[data-testid="stImage"] img {max-width: 100%; height: auto; object-fit: cover;}
  div[data-testid="stFileUploader"] {min-width: 0;}
  div[data-testid="stForm"] {border: 1px solid rgba(120,130,150,.20); border-radius: 18px; padding: 1.25rem; background: rgba(120,130,150,.035);}
  .auth-hero {padding: 1.6rem; border-radius: 20px; background: linear-gradient(135deg, #173a63, #356d9b); color: white; min-height: 100%;}
  .auth-hero p {color: rgba(255,255,255,.88); line-height: 1.6;}
  .auth-eyebrow {text-transform: uppercase; letter-spacing: .12em; font-size: .78rem; font-weight: 700; color: #b9d9f7;}
  .auth-feature {padding: .65rem .8rem; margin-top: .6rem; border: 1px solid rgba(255,255,255,.22); border-radius: 12px; background: rgba(255,255,255,.07);}
  .profile-card {padding: 1rem; border: 1px solid rgba(120,130,150,.20); border-radius: 18px; background: rgba(120,130,150,.035);}
  [data-testid="stMetric"] {background: rgba(120,120,120,.07); padding: 14px 16px; border-radius: 14px; border: 1px solid rgba(120,120,120,.16);}
  /* Keep every navigation tab visible by wrapping tabs onto multiple rows. */
  div[data-testid="stTabs"] [data-baseweb="tab-list"],
  div[data-testid="stTabs"] [role="tablist"] {
    display: flex !important;
    flex-wrap: wrap !important;
    overflow-x: visible !important;
    white-space: normal !important;
    gap: 0.25rem 0.45rem !important;
    height: auto !important;
  }
  div[data-testid="stTabs"] [data-baseweb="tab"] {
    flex: 0 0 auto !important;
    white-space: normal !important;
    min-height: 2.5rem !important;
  }
  div[data-testid="stTabs"] button {font-weight: 600;}
  div.stButton > button, div.stFormSubmitButton > button {border-radius: 12px; font-weight: 650; min-height: 3rem;}
  div[data-testid="stChatMessage"] {border-radius: 14px;}
  [data-testid="stSidebar"] div.stButton > button {min-height: 2.05rem !important; padding: .28rem .35rem !important; font-size: .82rem !important; line-height: 1.15 !important; border-radius: 9px !important; white-space: normal !important;}
  [data-testid="stSidebar"] [data-testid="stSelectbox"] {margin-bottom: .25rem;}
  [data-testid="stSidebar"] hr {margin: .45rem 0;}
  .sidebar-user {padding:.65rem .7rem;border-radius:12px;background:rgba(100,120,150,.10);margin-bottom:.5rem;}
  .public-info-card {height:100%;}

  .portal-hero {padding: 1.1rem 1.25rem; border: 1px solid rgba(120,120,120,.18); border-radius: 18px; background: linear-gradient(120deg, rgba(80,130,220,.10), rgba(80,190,170,.07)); margin-bottom: .75rem;}
  .portal-subtitle {color: #747985; font-size: .95rem;}
  div[data-testid="stImage"] img {border-radius: 16px; display: block;}
</style>
""", unsafe_allow_html=True)

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
if not API_KEY:
    st.error("Gemini API key missing. Set GEMINI_API_KEY in your .env file.")
    st.stop()
client = genai.Client(api_key=API_KEY)

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
    """Optional: create/update the configured admin using secrets stored in .env."""
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not username or not password:
        return
    with db_connect() as conn:
        row = conn.execute("SELECT username, role FROM students WHERE username = ?", (username,)).fetchone()
        if row:
            # Never reset the admin password on every Streamlit rerun.
            conn.execute("UPDATE students SET role='admin' WHERE username=?", (username,))
        else:
            conn.execute(
                """INSERT INTO students (username, password, name, fee_status, course, email, role)
                   VALUES (?, ?, ?, 'N/A', 'Administrator', NULL, 'admin')""",
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
    if not audio_bytes:
        return None
    recognizer = sr.Recognizer()
    try:
        seg = AudioSegment.from_file(BytesIO(audio_bytes))
        wav_io = BytesIO()
        seg.export(wav_io, format="wav")
        wav_io.seek(0)
        with sr.AudioFile(wav_io) as source:
            audio_data = recognizer.record(source)
        return recognizer.recognize_google(
            audio_data, language=st.session_state.selected_language_code
        )
    except sr.UnknownValueError:
        st.warning("Could not understand the audio. Please try again.")
        return None
    except Exception as e:
        st.error(f"Audio processing failed. Ensure FFmpeg is installed. Details: {e}")
        return None

def text_to_audio_autoplay(text, lang_code):
    try:
        tts = gTTS(text=text, lang=lang_code, slow=False)
        audio_bytes = BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        b64 = base64.b64encode(audio_bytes.read()).decode()
        return f'<audio autoplay controls><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
    except Exception as e:
        st.warning(f"Could not generate audio: {e}")
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
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            contents=user_query,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
                max_output_tokens=700,
            ),
        )
        return (response.text or "").strip() or "I couldn't generate a response. Please try rephrasing your question."
    except Exception as e:
        error_text = str(e)
        if "404" in error_text or "NOT_FOUND" in error_text:
            return "The configured Gemini model is unavailable for this API key. Check GEMINI_MODEL in .env (recommended: gemini-3.8-flash) and confirm the key is valid."
        if "401" in error_text or "403" in error_text or "API_KEY_INVALID" in error_text:
            return "Gemini rejected the API key. Check GEMINI_API_KEY in .env; do not share the key in chat or screenshots."
        return f"I couldn't reach the AI service just now. Please try again. (Details: {error_text[:220]})"

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
    st.markdown("""
    <div class="auth-hero">
      <div class="auth-eyebrow">Greater Noida Institute of Technology</div>
      <h1 style="margin:.5rem 0 .35rem 0;color:white">🎓 GNIT Student Portal</h1>
      <p style="font-size:1.05rem;margin-bottom:1rem">One place for academic support, campus information, attendance, assignments, and student services.</p>
      <div class="auth-feature">🤖 <b>AI Help Desk</b> — get help with college-related questions</div>
      <div class="auth-feature">📚 <b>Academic services</b> — timetable, faculty, library, and announcements</div>
      <div class="auth-feature">👤 <b>Your student space</b> — profile, attendance, assignments, and queries</div>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    auth_left, auth_right = st.columns([1, 1.15], gap="large")
    with auth_left:
        st.subheader("Welcome back")
        st.write("Sign in to continue to your student dashboard.")
        with st.form("login_form", border=False):
            login_username = st.text_input("Username", key="login_username", placeholder="Enter your username")
            login_password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
            login_submit = st.form_submit_button("🔐  Sign in", use_container_width=True, type="primary")
        if login_submit:
            user = verify_login(login_username, login_password)
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user["username"]
                st.session_state.student_name = user["name"]
                st.session_state.user_role = user["role"]
                st.session_state.messages = []
                st.rerun()
            else:
                st.error("We couldn't sign you in. Check your username and password, then try again.")
        st.caption("Administrator access is managed separately by the project owner.")
    with auth_right:
        st.subheader("New to the portal?")
        st.write("Create your student account to access college services.")
        with st.form("register_form", clear_on_submit=False, border=False):
            new_name = st.text_input("Full name", placeholder="As shown on your college records")
            new_username = st.text_input("Choose a username", placeholder="At least 3 characters")
            new_email = st.text_input("College or personal email", placeholder="you@example.com")
            new_course = st.selectbox(
                "Course / programme",
                ["B.Tech CSE", "B.Tech IT", "B.Tech ECE", "B.Tech Mechanical", "MBA", "MCA", "Other"]
            )
            new_password = st.text_input("Create password", type="password", help="Use at least 10 characters.")
            confirm_password = st.text_input("Confirm password", type="password")
            register_submit = st.form_submit_button("✨  Create student account", use_container_width=True, type="primary")
        if register_submit:
            if new_password != confirm_password:
                st.error("Passwords do not match. Please re-enter them.")
            else:
                ok, message = register_student(
                    new_name, new_username, new_email, new_password, new_course
                )
                (st.success if ok else st.error)(message)
                if ok:
                    st.info("Your account is ready. Select the sign-in form and log in with your new credentials.")

    st.divider()
    faq_col, reset_col = st.columns([1.15, 1], gap="large")
    with faq_col:
        with st.expander("❓ Frequently asked questions", expanded=True):
            st.caption("Quick answers before you sign in")
            if {"question", "answer"}.issubset(set(faq_df.columns)):
                for _, faq_row in faq_df.fillna("").iterrows():
                    with st.expander(str(faq_row["question"])):
                        st.write(str(faq_row["answer"]))
            else:
                st.info("FAQs are unavailable because faqs.csv must contain 'question' and 'answer' columns.")
    with reset_col:
        with st.expander("🔑 Forgot your password?", expanded=False):
            st.write("Submit a password-reset request. For your security, the portal will not reveal whether an account exists. An administrator will verify the request and provide a temporary password through an approved channel.")
            with st.form("forgot_password_form", clear_on_submit=True):
                reset_identity = st.text_input("Username or registered email", placeholder="Enter your username or email")
                reset_submit = st.form_submit_button("Request password reset", use_container_width=True, type="primary")
            if reset_submit:
                identity = reset_identity.strip()
                if identity:
                    with db_connect() as conn:
                        found = conn.execute("SELECT username, email FROM students WHERE (lower(username)=lower(?) OR lower(email)=lower(?)) AND role != 'admin'", (identity, identity)).fetchone()
                        if found:
                            pending = conn.execute("SELECT id FROM password_reset_requests WHERE username=? AND status='Pending'", (found["username"],)).fetchone()
                            if not pending:
                                conn.execute("INSERT INTO password_reset_requests(username,email) VALUES(?,?)", (found["username"], found["email"]))
                            conn.commit()
                    st.success("If the details match a student account, a reset request has been recorded. Please contact the college portal administrator for verification.")
                else:
                    st.warning("Enter your username or registered email to continue.")
    st.divider()
    st.subheader("🏛️ About GNIT")
    with db_connect() as conn:
        public_info = {r["section"]: dict(r) for r in conn.execute("SELECT section,title,content FROM college_info WHERE section IN ('about','mission','vision','history')").fetchall()}
    public_cols = st.columns(2)
    for col, key, fallback in [
        (public_cols[0], "about", "College overview will be published by the administrator."),
        (public_cols[1], "mission", "The official mission statement will be published by the administrator."),
    ]:
        with col:
            with st.container(border=True):
                st.markdown("#### " + public_info.get(key, {}).get("title", {"about":"About the college","mission":"Our mission"}[key]))
                st.write(public_info.get(key, {}).get("content") or fallback)
    with st.container(border=True):
        st.markdown("#### " + public_info.get("vision", {}).get("title", "Our vision"))
        st.write(public_info.get("vision", {}).get("content") or "The official vision statement will be published by the administrator.")
        st.markdown("#### " + public_info.get("history", {}).get("title", "History and founding"))
        st.write(public_info.get("history", {}).get("content") or "Verified founding details will be published by the administrator. No founding date or founder is assumed by this portal.")
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
    admin_tabs = st.tabs(["Students & security", "Password resets", "Attendance", "Assignments", "Student queries", "Timetable", "Faculty", "Holidays", "Library", "Campus locations", "Announcements", "Fees & student summary", "College information", "Placements", "Campus life & events", "Assignment submissions"])

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

    with admin_tabs[2]:
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

    with admin_tabs[3]:
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

    with admin_tabs[4]:
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

    with admin_tabs[5]:
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

    with admin_tabs[6]:
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

    with admin_tabs[7]:
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

    with admin_tabs[8]:
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

    with admin_tabs[9]:
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

    with admin_tabs[10]:
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
    with admin_tabs[11]:
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

    with admin_tabs[12]:
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

    with admin_tabs[13]:
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

    with admin_tabs[14]:
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

    with admin_tabs[15]:
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
    clear_col, timetable_col = st.columns(2)
    with clear_col:
        if st.button("🗑️ Clear chat", key="global_clear_chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.last_prompt = None
            st.rerun()
    with timetable_col:
        if st.button("🗓️ Timetable", key="global_toggle_timetable", use_container_width=True):
            st.session_state.show_timetable = not st.session_state.show_timetable
    st.markdown("##### 🎙️ Voice input")
    voice_input = mic_recorder(start_prompt="🎙️ Speak", stop_prompt="⏹️ Stop", key="voice_recorder_sidebar_global")
    if voice_input and voice_input.get("bytes"):
        st.session_state.voice_input = voice_input["bytes"]
    if st.session_state.show_timetable:
        student_timetable = get_course_timetable(student_data["course"])
        days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        st.caption("Weekly timetable")
        for day in days_order:
            st.caption(f"{day}: {student_timetable.get(day, 'Not published')}")
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

if active_section == "Campus map & rooms":
    st.subheader("📍 Campus locations and classroom directions")
    with db_connect() as conn: rows = conn.execute("SELECT name, building, room, details, map_url FROM campus_locations ORDER BY name").fetchall()
    if rows:
        for r in rows:
            with st.container(border=True):
                st.markdown(f"**{r['name']}**")
                st.write(" • ".join(str(v) for v in [r['building'], ('Room '+r['room']) if r['room'] else None] if v))
                if r['details']: st.write(r['details'])
                if r['map_url'] and str(r['map_url']).startswith(('https://','http://')): st.markdown(f"[Open map / directions]({r['map_url']})")
    else: st.info("Campus locations are not available yet. The administrator can add verified room and building directions.")

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
    with db_connect() as conn:
        companies=conn.execute("SELECT * FROM placement_companies ORDER BY visit_year DESC,name").fetchall()
    if companies:
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
    else: st.info("Placement company details will appear here after the administrator publishes verified company names and logos.")

if active_section == "Campus life":
    st.subheader("🏟️ Hostel, grounds, sports, and campus life")
    with db_connect() as conn: campus_rows=conn.execute("SELECT * FROM campus_content ORDER BY id DESC").fetchall()
    if campus_rows:
        for item in campus_rows:
            with st.container(border=True):
                st.markdown(f"#### {item['title']}")
                st.caption(item["category"])
                if item["details"]: st.write(item["details"])
                if item["media"]:
                    if item["media_type"] and item["media_type"].startswith("video/"): st.video(item["media"])
                    elif item["media_type"] and item["media_type"].startswith("image/"): st.image(BytesIO(item["media"]),use_container_width=True)
    else: st.info("Hostel, sports, ground, and fest information will be published here by the administrator.")

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
>>>>>>> bc64060 (Prepare AI college help desk for GitHub)

