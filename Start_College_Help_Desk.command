#!/bin/bash
# Launch GNIT College Help Desk from this folder.
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Virtual environment (.venv) not found in this folder."
  echo "Please make sure this launcher is inside your project folder."
  read -r -p "Press Return to close..."
  exit 1
fi

source ".venv/bin/activate"

if [ ! -f "app.py" ]; then
  echo "app.py not found. Check that this launcher is inside your project folder."
  read -r -p "Press Return to close..."
  exit 1
fi

python3 -m streamlit run app.py
