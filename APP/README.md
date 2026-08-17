# Job Tracker

A simple application for tracking job applications, organizing opportunities, and keeping the search process in one place.

## Overview

Job Tracker is designed to help manage the job search workflow by storing application details, tracking statuses, and keeping related information organized in a single project.

## Features

- Track job applications in one place.
- Organize companies, roles, and application dates.
- Monitor progress through stages such as applied, interview, offer, or rejected.
- Keep notes and follow-up details for each opportunity.
- Reduce reliance on spreadsheets for job search management.

## Tech Stack

- **Backend:** FastAPI, Uvicorn, Motor/PyMongo (MongoDB), Pydantic
- **Auth:** PyJWT, bcrypt
- **Scheduling:** APScheduler
- **Integrations:** Mailgun (email, via REST), ClickSend (SMS, via REST), Google Gemini (screenshot OCR)
- **Reporting:** pypdf (fills the IDES ADJ034F form)
- **Frontend:** React 19, React Router, Tailwind CSS, shadcn/ui, Recharts

> The full, pinned dependency list lives in `backend/requirements.txt`
> (runtime) and `backend/requirements-dev.txt` (tests). It is intentionally
> not duplicated here so the two cannot drift apart.

## Getting Started

### Prerequisites

- Python
- Node.js
- MongoDB
- npm

### Installation

Step 1. Install Python 3.11+ - make sure to check "Add Python to PATH" during install on Windows. Open your terminal and navigate to your project folder and run the following commands:

```bash
sudo apt update
sudo apt install python3
python3 --version
```

Step 2. Install Node.js (v18 or later) + Yarn. Download Node from nodejs.org, then install Yarn by running in your terminal:

```bash
npm install -g yarn
```

Step 3. For the database, download from mongodb.com/try/download/community - the free Community edition is all you need. Install it and let it run as a service (it'll start automatically in the background).

Optionally grab MongoDB Compass (a visual GUI for the database) - very helpful for a beginner to see what's actually stored.


Step 4. Clone the repository. In your terminal run the following command:

```bash
git clone https://github.com/cagedbear83/job-tracker.git
cd job-tracker
```

Step 5. Create the environment. Open your terminal, navigate to your project folder, and run the following command:

```bash
# Replace ".venv" with any name you prefer for your environment folder
python -m venv .venv
```

Step 6. Create the app running. Open two terminal windows - one for the backend, one for the frontend.

Terminal 1 - Backend:

```bash
cd "job-tracker/APP/backend"
pip install -r requirements.txt
uvicorn server:app --reload --port 8001
```

Terminal 2 - Frontend:

```bash
cd "job-tracker/APP/frontend"
yarn install
yarn start
```

## Usage

1. Create or sign-in to an account.
2. Add a new job application.
3. Update the application status as the process moves forward.
4. Review saved opportunities, notes, and follow-up items.
5. Print or save PDF that adhere to IDES requirements.

## Project Structure

```
job-tracker/
├── APP/
│   ├── backend/
│   │   ├── assets/
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   ├── requirements-dev.txt
│   │   └── server.py
│   └── frontend/
│       ├── src/
│       │   └── pages/
│       ├── components.json
│       ├── craco.config.js
│       ├── jsconfig.json
│       ├── package.json
│       ├── postcss.config.js
│       ├── README.md
│       ├── tailwind.config.js
│       └── yarn.lock
├── design_guidelines.json
└── README.md
```

## Screenshots

Add screenshots or a short demo GIF here once the interface is ready.

```md
![Dashboard screenshot](path/to/screenshot.png)
```

## Roadmap

- Add authentication.
- Add filtering and search.
- Add dashboard analytics.
- Add reminders for follow-ups.
- Add export/import support.

## Contributing

Contributions, ideas, and improvements are welcome. Open an issue to discuss changes or submit a pull request when the contribution workflow is ready.

## License

MIT License

Copyright (c) 2026 Kyle Gagen

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
