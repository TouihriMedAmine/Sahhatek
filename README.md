# Sahatek – Your Personal Emergency & Health AI

Sahatek is an AI-powered assistant designed to help you handle emergencies, understand symptoms, and get fast, precise medical guidance.

## Features

- **🚑 Emergency Guidance**: Instant steps to follow during emergencies (asphyxia, bleeding, poisoning, etc.).
- **🩺 Symptom Checker**: Describe your symptoms and get structured medical guidance.
- **📘 Medical Knowledge Base**: Instant answers from a large curated emergency knowledge base.
- **💬 Real-Time Chat**: Chat naturally and get fast, contextual responses.
- **🔒 Secure & Private**: Your data stays private.

## Tech Stack

- **Backend**: Django (Python) / version 3.12
- **Frontend**: HTML, Tailwind CSS, JavaScript
- **Database**: SQLite

## Installation

1.  **Clone the repository** (if applicable) or navigate to the project directory.

2.  **Install Python dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
 or 
pip install Django==5.2.0 django-tailwind==3.8.0
pip install httpx==0.27.0 requests==2.31.0
pip install openai==1.12.0 geopy==2.4.1
pip install spacy==3.8.1
python -m spacy download en_core_web_sm
pip install sentence-transformers==2.2.2 transformers==4.36.2
pip install torch==2.4.0 torchvision==0.18.1 torchaudio==2.4.0
pip install faiss-cpu==1.13.1 numpy==1.26.3 rapidfuzz==3.6.1
pip install flask==3.0.0 flask-cors==4.0.0
pip install fastapi==0.109.0 uvicorn[standard]==0.27.0 pydantic==2.5.3
pip install vosk==0.3.45 sounddevice==0.4.6
pip install gradio==4.8.0 python-dotenv==1.0.0

3.  **Install Node.js dependencies** (for Tailwind CSS):
    ```bash
    npm install
    ```

4.  **Apply database migrations**:
    ```bash
    python manage.py migrate
    ```

5.  **Create a superuser** (optional, for admin access):
    ```bash
    python manage.py createsuperuser
    ```

## Usage

1.  **Start the development server**:
    ```bash
    python manage.py runserver
    ```

2.  **Access the application**:
    Open your browser and go to `http://127.0.0.1:8000/`.

3.  **Tailwind CSS**:
    If you make changes to the CSS, you can watch for changes with:
    ```bash
    npx tailwindcss -i ./static/css/style.css -o ./static/css/output.css --watch
    ```

## Project Structure

- `agents/`: AI orchestration logic.
- `sahatek/`: Main project settings and URL configuration.
- `static/`: Static files (CSS, JS, Images).
- `templates/`: HTML templates.
- `users/`: User management (Authentication, Profiles).
