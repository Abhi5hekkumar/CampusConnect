# GNIT College Help Desk — Phase 13
## Campus navigation UI + natural neural assistant voice

### Changes
- Removed the driving option and destination dropdown from Campus Map & Rooms.
- Replaced them with five clear destination cards: Library, Girls' Hostel, Boys' Hostel, Canteen, and Academic Block.
- Each destination opens Google Maps walking directions, which can use the student's current GPS location after permission is granted.
- Replaced gTTS playback with Edge TTS neural voices. English uses `en-US-AriaNeural` for a natural, polished assistant-style voice. Hindi, French, German, and Spanish have corresponding neural voice choices.

### Install
1. Stop Streamlit (`Control-C`) and back up `app.py`.
2. Extract this ZIP into the project folder, replacing `app.py` and `requirements-groq.txt`.
3. Keep `.env`, `.venv`, `students.db`, and `faqs.csv`.
4. Install dependencies:
   `./.venv/bin/python -m pip install -r requirements-groq.txt`
5. Run:
   `./.venv/bin/python -m streamlit run app.py`

### Notes
- Edge TTS requires internet access; audio is generated online.
- Browser/device location permission is required for Google Maps to start from current location.
- The app uses the standard Google Maps directions URL; internal building pins may need exact campus coordinates for more precise destination placement.
