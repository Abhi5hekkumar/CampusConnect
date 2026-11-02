# GNIT College Help Desk — Phase 9 UI and role-selection update

## What changed
- Replaces the large decorative feature panel with a compact, professional portal header.
- Adds selectable Student, Teacher / Faculty, and Administrator portal options.
- Student login and registration are presented as separate tabs; registration fields appear when selected.
- Adds faculty access request form and pending approval workflow.
- Adds a visible administrator sign-in option; only the configured admin account can enter the admin dashboard.
- Adds a faculty workspace for approved faculty to publish announcements and assignments.
- Moves About, Mission, Vision, and History into separate tabs so the page remains compact and each information section can scroll independently.
- Keeps the existing student/admin sections and existing database file path.

## Install safely
1. Stop Streamlit with Control+C.
2. In your project folder, back up the current file: `cp app.py app_before_phase9.py`
3. Copy this bundle's `app.py` over the existing `app.py` only.
4. Do not replace `.env`, `.venv`, `students.db`, `faqs.csv`, or `requirements.txt`.
5. Start with `./.venv/bin/python -m streamlit run app.py`.

The app requires the existing `GEMINI_API_KEY` setting in `.env`. Keep secrets private. Test with a separate faculty test account before using real staff accounts.
