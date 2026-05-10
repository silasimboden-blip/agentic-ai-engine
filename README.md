# Agentic AI Engineering

This guide walks you through setting up a GCP account, the Google Cloud CLI, and the agentic AI application that we will extend throughout the lecture. Follow all steps in order. By the end you will have the application running locally — a greeting agent will be ready to answer your questions and help you prepare for the upcoming sessions.

## 1. Prerequisites

Install
- [Python 3.14](https://www.python.org/downloads/)
  - **Windows:** check "Add Python to PATH" during installation, or set manually:
    - `PATH` — add `C:\Users\<YOU>\AppData\Local\Programs\Python\Python314\` and `...\Scripts\`
    - `PYTHONPATH` — (optional) path to your project root so imports resolve correctly
  - **macOS / Linux:** Python is typically available on `PATH` automatically after install
- Create a [Google Cloud Platform](https://console.cloud.google.com) account if you don't already have one
- Install [Google Cloud CLI](https://docs.cloud.google.com/sdk/docs/install-sdk) following the instructions in the link.

## 2.1. Create a GCP project

1. Go to [Google Cloud Console — New Project](https://console.cloud.google.com/projectcreate)
2. Enter a **Project name** (e.g. `agentic-ai-engineering`)
3. Select a **Billing account** (required for Vertex AI and Cloud Run)
4. Click **Create** and wait for the project to be provisioned
5. Note your **Project ID** (shown below the project name) — you will need it in later steps

> **Tip:** The project ID is immutable and globally unique. It may differ from the project name.

## 2.2 Set a GCP billing limit

1. Open the [Google Cloud Console - Billing](https://console.cloud.google.com/billing)
2. Select the **billing account** linked to your project
3. In the left menu, click **Budgets & Alerts**
4. Click **Create Budget**
5. Choose:
   - **Scope:** Billing account or project
   - **Budget amount:** e.g. $50/month
6. Set **alert thresholds:** 50%, 90%, 100%

This will notify you by email when spending reaches each threshold.


## 2.3 Google Login & Authentication

Initialize gcloud and log in:

```bash
gcloud init
```

List authenticated accounts:

```bash
gcloud auth list
```

If necessary, switch to the correct account:

```bash
gcloud config set account <YOUR_ACCOUNT_EMAIL>
```

Verify the active project:

```bash
gcloud config get-value project
```

Set the active project, if necessary:

```bash
gcloud config set project <PROJECT_ID>
```

Log in and create Application Default Credentials (ADC):

```bash
gcloud auth application-default login
```

Set the ADC quota project, if a corresponding error message appears:

```bash
gcloud auth application-default set-quota-project <PROJECT_ID>
```

> **Note:** The ADC credentials file is saved at:
> - **Windows:** `%APPDATA%\gcloud\application_default_credentials.json`
> - **macOS / Linux:** `~/.config/gcloud/application_default_credentials.json`
>
> Add this path to your `.env` as `GOOGLE_APPLICATION_CREDENTIALS`.

More help: [gcloud CLI cheat sheet](https://docs.cloud.google.com/sdk/docs/cheatsheet)

### Create a Cloud Storage bucket

Create a bucket to store agent artifacts:

```bash
gcloud storage buckets create gs://<BUCKET_NAME> \
  --project=<PROJECT_ID> \
  --location=europe-north1 \
  --uniform-bucket-level-access
```

Replace `<BUCKET_NAME>` with a globally unique name (e.g. `agentic-ai-eng-<PROJECT_ID>`), then set it in `.env`:

```env
GOOGLE_CLOUD_STORAGE_BUCKET=<BUCKET_NAME>
```

> **Note:** Bucket names are globally unique across all GCP projects. A common convention is to include your project ID in the name to avoid conflicts.

## Enable Vertex AI API

Enable the [Vertex AI API](https://console.cloud.google.com/apis/enableflow?apiid=aiplatform.googleapis.com) by following the instruction in the link.


## 3. IDE Setup — VS Code (Recommended)

Install [Visual Studio Code](https://code.visualstudio.com/) and open the project folder.

### Create the virtual environment and select the interpreter

VS Code can create the `.venv` and register the Python interpreter in one step — no terminal required:

1. Open the Command Palette: `Ctrl+Shift+P`
2. Type **Python: Create Environment** and press Enter
3. Select **Venv**
4. Select **Python 3.14.x** as the base interpreter
5. When asked which dependencies to install, tick **`pyproject.toml`** — VS Code will install all packages automatically

VS Code sets the new environment as the active interpreter immediately. You will see **('.venv': venv)** in the status bar at the bottom-left. New terminals opened inside VS Code will have the environment activated automatically.

> **Tip:** If you already created the `.venv` via the terminal, use **Python: Select Interpreter** instead and choose the **('.venv': venv)** entry.

Activate the virtual environment:

**Windows (PowerShell):**
```powershell
& .\.venv\Scripts\Activate.ps1
```

**macOS / Linux (bash / zsh):**
```bash
source .venv/bin/activate
```

## 4. Project Setup

Install [uv](https://docs.astral.sh/uv/):

```bash
pip install uv
```

Install dependencies and set up the project:

```bash
uv lock
uv sync
uv pip install -e .
```

## 5. Configure `.env`

Copy the example and fill in your values:

```bash
cp .env.example .env
```

Required variables:

- `GOOGLE_APPLICATION_CREDENTIALS` — path to your ADC credentials file
- `GOOGLE_CLOUD_PROJECT` — your GCP project ID
- `GOOGLE_CLOUD_STORAGE_BUCKET` — your Cloud Storage bucket name

## 6. Run the Application locally

```bash
uvicorn agentic_ai_main:app --reload --port 8000
```

The application will be available at **http://localhost:8000**. The chat interface is served at the root path `/`.


