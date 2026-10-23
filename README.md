# College Voice Chatbot 🎓

An AI-powered college assistant built with Python and Streamlit to help students access academic information through conversational text and voice interactions.

**Project Status:** 🚧 Active Development

## About the Project

College Voice Chatbot is a work-in-progress application designed to make college-related information easier to access. It combines Google's Gemini AI with student-oriented academic features and voice interaction capabilities.

The project is being developed incrementally, with new features, refinements, and improvements planned over time.

## Features

- **AI-Powered Chatbot:** Generates conversational responses using Google's Gemini API.
- **Student Authentication:** Student registration and login functionality.
- **Voice Input:** Supports speech-based interaction.
- **Text-to-Speech:** Converts responses into audio.
- **Frequently Asked Questions:** Provides college-related information using an FAQ dataset.
- **Academic Information:** Includes features for timetables, attendance, and assignments.
- **Role-Based Portals:** Supports student, faculty, and administrator workflows.
- **Database Integration:** Uses SQLite for application data.
- **Multilingual Support:** Includes language-related capabilities that are being refined.

*Features may be incomplete or subject to change during development.*

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application logic |
| Streamlit | User interface |
| Google Gemini API | AI-generated responses |
| SQLite | Data storage |
| Pandas | Data processing |
| SpeechRecognition | Speech recognition |
| gTTS | Text-to-speech |
| streamlit-mic-recorder | Microphone input |
| pydub | Audio processing |
| bcrypt | Password hashing |
| python-dotenv | Environment configuration |

## Getting Started

### Prerequisites

- Python installed on your system
- pip package manager
- A Google Gemini API key for AI functionality
- FFmpeg and compatible audio dependencies for relevant voice features

### Installation

1. Clone the repository:

   ```bash
   git clone YOUR_GITHUB_REPOSITORY_URL
   cd YOUR_PROJECT_DIRECTORY
   ```

2. Create a virtual environment:

   ```bash
   python -m venv .venv
   ```

3. Activate the environment.

   **macOS/Linux:**

   ```bash
   source .venv/bin/activate
   ```

4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Configure your `GEMINI_API_KEY` locally using an environment variable or a `.env` file. Never commit real API keys or passwords.

6. Start the application:

   ```bash
   streamlit run app.py
   ```

Additional setup may be required depending on the features you use.

## Project Structure

```text
college-voice-chatbot/
├── app.py
├── faqs.csv
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── LICENSE
├── modules/
└── screenshots/
```

The structure will evolve as the project grows. Some folders may be added as development continues.

## Development Roadmap

- Improve authentication and authorization.
- Expand the FAQ dataset and academic information.
- Refine voice recognition and multilingual interactions.
- Improve error handling and user experience.
- Organize code into reusable modules.
- Add automated tests.
- Improve database management and deployment readiness.
- Publish a stable public demo when the application is ready.

## Current Limitations

This project is under active development and is not yet presented as a production-ready college management system. Features, database setup, and deployment requirements may change as development progresses.

## Feedback

Suggestions, bug reports, and ideas for improvement are welcome.

## License

Refer to the `LICENSE` file for the applicable license terms.
