# GNIT College Help Desk — Phase 12
## Model 404 fix + campus directions

### What's changed
- Groq chat tries the configured `GROQ_MODEL` first, then `openai/gpt-oss-120b`, then `llama-3.1-8b-instant` if the configured model is missing or decommissioned.
- Campus map & rooms now includes selectable destinations: Library, Girls' Hostel, Boys' Hostel, Canteen, and Academic Block.
- Students choose walking or driving and open Google Maps directions. Google Maps uses the device's current location after the student grants browser location permission.
- Existing campus location records remain visible below the directions.

### Install
1. Stop Streamlit (`Control-C`).
2. Back up your current `app.py`.
3. Extract this ZIP into your project folder, replacing `app.py` and adding/updating `campus_images/` as included.
4. Keep `.env`, `.venv`, `students.db`, and `faqs.csv`.
5. In `.env`, remove the stale `GROQ_MODEL=llama-3.3-70b-versatile` line or set:
   `GROQ_MODEL=openai/gpt-oss-120b`
6. Install dependencies if needed:
   `./.venv/bin/python -m pip install -r requirements-groq.txt`
7. Run:
   `./.venv/bin/python -m streamlit run app.py`

### Location behavior
The app cannot silently access GPS. Students must allow location permission in their browser/device. The directions link opens Google Maps, which can then use the live location and navigation. If location permission is denied, Google Maps can still route after the student selects their starting point.

### Model note
Model IDs and availability can vary by account. If fallback models are unavailable to your key, verify active IDs in Groq Console and update `GROQ_MODEL`.
