#!/bin/bash
cd "$(dirname "$0")"
echo "Starting College Voice Chatbot..."
python3 -m streamlit run app.py
echo ""
echo "Chatbot stopped. Press any key to close."
read -n 1
