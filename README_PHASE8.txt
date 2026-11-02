GNIT College Help Desk — Phase 8 Role Portal

What changed in app.py:
- Role selector on login: Student, Teacher/Faculty, Administrator.
- Existing student registration and student dashboard retained.
- Faculty access request form with department, designation, optional employee ID, password, and verification note.
- Faculty requests create inactive faculty accounts; requests cannot self-approve.
- New administrator tab to review, approve, or reject faculty requests.
- Approved faculty get a separate faculty portal with announcement publishing, assignment creation, department details, and student-query response workflow.
- Existing administrator dashboard sections retained, with Faculty approvals added.
- Existing database tables and data are preserved; a new faculty_requests table is created automatically.

IMPORTANT SAFE INSTALL
1. Stop Streamlit with Control-C in Terminal.
2. In Finder, open your current project folder and make a backup copy of app.py (for example app_before_phase8.py).
3. Keep students.db, .env, .venv, faqs.csv, requirements.txt and all existing files. Do not replace or delete them.
4. Copy the app.py from this package into your current project folder, replacing only app.py after the backup.
5. Keep your existing .env private. Ensure it already contains GEMINI_API_KEY. For administrator login, ensure ADMIN_USERNAME and ADMIN_PASSWORD are configured. Never paste these values into chat.
6. Start the app using: ./.venv/bin/python -m streamlit run app.py
7. Test student login first, then administrator login. Use a separate test account for faculty registration and approve it from the administrator dashboard.

Security note: Selecting Administrator in the login form does not grant administrator access. The database role must already be admin, configured through the existing environment bootstrap.
