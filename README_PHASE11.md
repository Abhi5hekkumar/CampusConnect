# GNIT College Help Desk — Phase 11

## What's included
- Keeps the Phase 10 Groq chat integration and professional UI.
- Fixes microphone transcription by sending recorded audio to Groq Whisper, so local `ffprobe`/FFmpeg is not required for the primary transcription path. Text chat remains available if voice transcription fails.
- Adds a placement section with a clickable link to the official GNIOT placement website.
- Adds the supplied hostel/campus photographs and a campus-life gallery.
- Adds hostel accommodation and amenities text in the Campus life section.

## Safe install
1. Stop Streamlit (`Control-C`).
2. Back up your current `app.py`.
3. Extract this ZIP into your project folder, replacing `app.py` and adding the `campus_images/` folder.
4. Keep your existing `.env`, `.venv`, `students.db`, `faqs.csv`, and `requirements.txt`.
5. Install/update Groq: `./.venv/bin/python -m pip install -r requirements-groq.txt`
6. In `.env`, set `GROQ_API_KEY`, `GROQ_MODEL`, and optionally `GROQ_AUDIO_MODEL`.
7. Run: `./.venv/bin/python -m streamlit run app.py`

## Notes
- No database migration is needed for these changes.
- The gallery photos are the images supplied for this project.
- Verify current hostel services, room types, and fees with the college before treating them as guaranteed.
- Placement link: https://www.gniotgroup.edu.in/placement.php
