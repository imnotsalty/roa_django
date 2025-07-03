Of course. Here is a comprehensive `README.md` file for your project.

This README is designed to be a complete guide, including the necessary background, installation instructions, API usage, and a special section detailing the troubleshooting steps we worked through. This will be invaluable for anyone (including your future self) setting up the project from scratch.

---

# AI Real Estate Marketing Designer

## Project Overview

This project is a Django-powered backend service that provides a conversational AI agent for real estate professionals at "Realty of America." The agent's primary purpose is to assist in the creation of professional marketing images (e.g., "Just Listed" ads, "Open House" flyers) with minimal user effort.

The agent engages in a natural conversation to gather necessary details like the property's MLS ID and the user's intent. It intelligently handles multi-step interactions where additional information (like an open house date) is required. The system uses a persistent, threaded conversation model, allowing users to continue their work across multiple API calls without resending the entire chat history.

## Key Features

-   **Conversational AI:** Utilizes LangChain and Google's Gemini models to understand user intent and drive the conversation.
-   **Dynamic Image Generation:** Integrates with the Bannerbear API to create customized marketing images based on real-time property data and user input.
-   **Stateful, Threaded Conversations:** Uses a PostgreSQL database to maintain conversation history and context, allowing for a seamless user experience via a simple `thread_id`.
-   **Asynchronous Task Handling:** Built with Celery and Redis to offload long-running tasks (like API calls to AI services and image renderers), ensuring the main web server remains responsive.
-   **Robust and Scalable:** Based on the `cookiecutter-drf` template, providing a solid foundation with best practices for production environments.

## Technology Stack

-   **Backend:** Django, Django REST Framework
-   **AI Orchestration:** LangChain
-   **Language Model:** Google Gemini
-   **Database:** PostgreSQL
-   **Task Queue:** Celery
-   **Message Broker:** Redis
-   **External APIs:** Bannerbear (Image Generation), Freeimage.host (Image Upload)

---

## Prerequisites

Before you begin, ensure you have the following installed on your system (these instructions are tailored for Debian/Ubuntu-based systems like Zorin OS):

1.  **Python 3.10+**
2.  **PostgreSQL Server:**
    ```bash
    sudo apt update
    sudo apt install postgresql postgresql-contrib libpq-dev
    ```
3.  **Redis Server:**
    ```bash
    sudo apt install redis-server
    ```
4.  **API Client:** A tool like [Postman](https://www.postman.com/downloads/) for testing the API endpoints.
5.  **API Keys:** You will need to sign up for and obtain keys from the following services:
    -   Google AI (for Gemini)
    -   Bannerbear
    -   Realty of America (Your internal API endpoint)
    -   Freeimage.host (Optional, for permanent image URLs)

---

## Setup and Installation

Follow these steps to get the project running locally.

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd roa_django
```

### 2. Set Up the Python Virtual Environment

It is highly recommended to use a virtual environment to manage project dependencies.

```bash
# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate
```

### 3. Configure the Database

You need to create a dedicated database and user for the application.

```bash
# Switch to the default postgres user
sudo -i -u postgres

# Create the database
createdb roa_django_db

# Create the user with a password prompt
# Use 'roa_django_user' as the username and provide a secure password
createuser --interactive --pwprompt
Enter name of role to add: roa_django_user
Enter password for new role: [your-secure-password]
Enter it again: [your-secure-password]
Shall the new role be a superuser? (y/n) y

# Exit the postgres user shell
exit
```

### 4. Install Python Dependencies

The `requirements.txt` file contains all necessary Python packages, including specific versions to avoid compatibility issues.

First, create the `requirements.txt` file:

```text
# requirements.txt
django
djangorestframework
psycopg2-binary
python-dotenv
dj-database-url
requests
langchain
langchain-google-genai
pydantic
celery
redis==3.5.3 # Pinned to a specific version to ensure compatibility with Celery
```

Now, install them all with one command:

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Create a `.env` file in the root of the project directory by copying the example below. Fill it in with your actual credentials.

```ini
# .env - Do NOT commit this file to version control

# Project Settings
SECRET_KEY='your-django-secret-key-here' # Generate a new one for production
DEBUG=True

# Database URL
# Format: postgres://USER:PASSWORD@HOST:PORT/NAME
DATABASE_URL="postgres://roa_django_user:[your-secure-password]@localhost:5432/roa_django_db"

# Celery & Redis Broker
CELERY_BROKER_URL="redis://localhost:6379/0"

# External API Keys
GOOGLE_API_KEY="your-google-api-key"
BANNERBEAR_API_KEY="your-bannerbear-api-key"
REALTY_API_ENDPOINT="your-realty-of-america-api-endpoint"
FREEIMAGE_API_KEY="your-freeimage-api-key"
```

### 6. Run Database Migrations

Apply the database schema to your newly created PostgreSQL database.

```bash
python manage.py migrate
```

---

## Running the Application

To run the application, you must start **three separate processes** in **three separate terminals**. Ensure your virtual environment is activated for each terminal.

### Terminal 1: Start Redis

First, ensure your Redis server is running.

```bash
sudo systemctl start redis-server
# You can check its status with:
sudo systemctl status redis-server
```

### Terminal 2: Start the Celery Worker

This process listens for and executes background tasks.

```bash
# Make sure your venv is active
source venv/bin/activate

# Start the worker
celery -A config.celery_app worker -l info
```
*(Note: If your main project folder is named `roa_django` instead of `config`, use `celery -A roa_django.celery_app worker -l info`)*

### Terminal 3: Start the Django Server

This is the main web application that will handle API requests.

```bash
# Make sure your venv is active
source venv/bin/activate

# Start the Django development server
python manage.py runserver
```

Your API is now running and accessible at `http://127.0.0.1:8000`.

---

## API Usage & Testing with Postman

### Endpoint

-   **URL:** `http://127.0.0.1:8000/api/v1/ai-designer/chat/`
-   **Method:** `POST`
-   **Headers:** `Content-Type: application/json`

### Scenario 1: Starting a New Conversation

To begin a conversation, send a request without a `thread_id`.

**Request Body:**

```json
{
    "user_input": "I need to create an open house ad for MLS ID 12345."
}
```

**Expected Response:**

The server creates a new conversation thread and returns a `thread_id`. The agent will likely ask for more information if the selected template requires it.

```json
{
    "role": "assistant",
    "content": "To complete the 'Open House' design, I just need a bit more information: the date of the open house (e.g., 'Saturday, June 15th') and the time of the open house (e.g., '2-4 PM'). Can you provide that for me?",
    "thread_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef"
}
```
**Important:** Copy the `thread_id` from the response for the next step.

### Scenario 2: Continuing the Conversation

To continue the chat, include the `thread_id` from the previous response in your next request.

**Request Body:**

```json
{
    "user_input": "It's this Friday from 4 PM to 6 PM.",
    "thread_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef"
}
```

**Expected Response:**

The server uses the `thread_id` to retrieve the conversation context and generates the final image.

```json
{
    "role": "assistant",
    "content": "Perfect! Using your details with the 'Open House' template, here is the final design:\n\n![Generated Ad](https://some.permanent.image.url/image.png)",
    "thread_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef"
}
```

---

## Developer Notes & Troubleshooting Guide

During development, we encountered several common setup issues. This section documents them for future reference.

### 1. The `ModuleNotFoundError: No module named 'celery'` Error

-   **Context:** This error occurs when first running `python manage.py runserver` after setting up the project.
-   **Reason:** The `cookiecutter-drf` template is pre-configured to use Celery for background tasks, which is a best practice for applications with long-running processes (like AI API calls). The project attempts to import `celery` on startup, but the package hasn't been installed yet.
-   **Solution:** Install `celery` and its message broker, `redis`, and run the worker as a separate process. The full installation steps are covered in the main guide.

### 2. The `AttributeError: 'NoneType' object has no attribute 'Redis'` Error

-   **Context:** This error occurs when trying to start the Celery worker (`celery -A ... worker ...`) even after installing the `celery` and `redis` packages.
-   **Reason:** This is a classic dependency version mismatch. The latest versions of the `redis` Python library (v4.x and newer) are not compatible with the version of `kombu` (a Celery dependency) that is installed. `kombu` expects the API from the older `redis` v3.x series.
-   **Solution:** Pin the `redis` library to a known compatible version. We must uninstall the new version and install the specific older one.
    ```bash
    # Uninstall the incompatible version
    pip uninstall redis

    # Install the compatible version
    pip install redis==3.5.3
    ```
    This is why the `requirements.txt` file explicitly lists `redis==3.5.3`.



Local run:
celery -A config.celery_app worker -l info

python manage.py runserver