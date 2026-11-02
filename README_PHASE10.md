# GNIT College Help Desk — Phase 10: Professional UI + Groq

## Included
- `app.py`: updated app with a polished, responsive Google-inspired Streamlit design.
- `requirements-groq.txt`: Groq SDK dependency.
- `.env.example`: environment variable names; replace placeholders locally.

## Safe installation
1. Stop Streamlit (`Control-C`).
2. Back up your current `app.py`.
3. Extract this ZIP into your existing project folder and allow `app.py` to replace the old one.
4. **Keep** `students.db`, `faqs.csv`, `.venv`, your existing `requirements.txt`, and your real `.env`.
5. Add `groq` to your existing requirements or run:
   `./.venv/bin/python -m pip install -r requirements-groq.txt`
6. In your private `.env`, replace `GEMINI_API_KEY` with `GROQ_API_KEY` and add:
   `GROQ_MODEL=llama-3.3-70b-versatile`
   Do not share or commit `.env`.
7. Start:
   `./.venv/bin/python -m streamlit run app.py`

## Notes
- This phase changes the AI text generation provider and visual styling; existing SQLite tables and workflows remain in place.
- Voice input, speech output, and FAQ behavior continue to use the existing libraries and code.
- If the configured Groq model is unavailable on your account, choose an active model in the Groq console and update `GROQ_MODEL`.
