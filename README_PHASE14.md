# Phase 14 — Map fix + PagePilot entry point

## Fix
Removed the unsupported `key=` argument from `st.link_button`, which caused the Campus Map page to crash on older Streamlit versions.

## PagePilot
Added **PagePilot Exam Prep** to the student Services navigation and a prominent Open PagePilot button. It currently links to the GitHub repository supplied by the project owner:
https://github.com/Abhi5hekkumar/PagePilot

**Important:** A GitHub repository is source code, not necessarily a live student-facing app. Replace the URL in `app.py` with the deployed PagePilot URL once available to open the actual application directly.

## Install
1. Stop Streamlit.
2. Back up `app.py`.
3. Extract this ZIP over the project folder, replacing `app.py`.
4. Keep `.env`, `.venv`, and the database files.
5. Run `./.venv/bin/python -m streamlit run app.py`.
