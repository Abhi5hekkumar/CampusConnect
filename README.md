# College Help Desk

An AI-assisted web portal that brings everyday college information and student services into one place.

Instead of walking between the library, accounts office and admin block to find out something simple, students can look it up online or ask the built-in AI assistant.

---

## Features

### Public (no login required)
- College information, vision and frequently asked questions

### Registered students
- Ask the AI assistant about college services, locations, the library and faculty
- Check whether a book is available in the library
- View faculty details and the holiday list
- Find academic blocks, hostels and other campus locations
- Check fee deposit status (view only, no online payments)
- Submit queries to the college
- Upload assignments and receive teacher feedback

### Teachers
- View submitted assignments and write feedback

---

## User Flow

- **Students:** Register, log in, then use the services above.
- **Assignments:** The student submits, the teacher reviews, and the feedback appears on the student's page.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python (Flask) |
| Database | MySQL |
| AI | Google Gemini API |
| Authentication | Session-based login |

---

## Project Structure

```text
AI-powered-student-college-helpdesk/
├── app.py                 # Flask application entry point
├── modules/               # Chatbot logic and supporting code
├── templates/             # HTML pages
├── static/                # CSS, JavaScript and images
├── screenshots/           # Images used in this README
├── requirements.txt       # Python dependencies
├── .env.example           # Template for environment variables
├── .gitignore
├── LICENSE
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.9 or newer
- MySQL server
- A Google Gemini API key

### 1. Clone the repository

```bash
git clone https://github.com/Abhi5hekkumar/AI-powered-student-college-helpdesk.git
cd AI-powered-student-college-helpdesk
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` and fill in your own values:

```env
GEMINI_API_KEY=your_api_key_here
DB_HOST=localhost
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=your_db_name
SECRET_KEY=change_me
```

Never commit your real `.env` file.

### 5. Set up the database

Create the MySQL database and import the schema file included in the project (add the exact command here, for example `mysql -u <user> -p <db_name> < schema.sql`).

### 6. Run the application

```bash
python app.py
```

Then open the address shown in the terminal (usually http://127.0.0.1:5000).

---

## Screenshots

![Home page](screenshots/home.png)
![AI assistant](screenshots/chat.png)
![Student dashboard](screenshots/student-dashboard.png)

---

## Security and Privacy Notes

- API keys and passwords are kept in a `.env` file, which is excluded from the repository.
- Only teachers can review submitted assignments.
- Students can only see their own records.
- Demo data in this repository is fictional.

---

## Roadmap

- Multilingual assistant
- Interactive campus map
- Assignment deadline reminders and feedback notifications
- Query status tracking
- Library book reservation

---

## License

Released under the [MIT License](LICENSE).

---

## Author

**Abhishek Kumar**

- GitHub: [Abhi5hekkumar](https://github.com/Abhi5hekkumar)
- LinkedIn: [Abhishek Kumar](https://www.linkedin.com/in/abhishek-kumar-94888b276)
- Email: kumarabhishek8749@gmail.com
