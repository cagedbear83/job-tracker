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

- aiohappyeyeballs==2.6.2
- aiohttp==3.13.5
- aiohttp-retry==2.9.1
- aiosignal==1.4.0
- annotated-doc==0.0.4
- annotated-types==0.7.0
- anyio==4.13.0
- APScheduler==3.11.2
- asn1crypto==1.5.1
- attrs==26.1.0
- bcrypt==5.0.0
- cachetools==7.1.4
- certifi==2026.5.20
- cffi==2.0.0
- charset-normalizer==3.4.7
- click==8.4.1
- colorama==0.4.6
- cryptography==48.0.0
- dataclass-wizard==0.39.1
- diskcache==5.6.3
- dnslib==0.9.26
- dnspython==2.8.0
- docker==7.1.0
- email-validator==2.3.0
- fastapi==0.136.3
- frozenlist==1.8.0
- h11==0.16.0
- h5py==3.16.0
- idna==3.16
- Jinja2==3.1.6
- llama_cpp_python==0.3.21
- localstack==2026.5.0
- markdown-it-py==4.2.0
- MarkupSafe==3.0.3
- mdurl==0.1.2
- motor==3.7.1
- multidict==6.7.1
- numpy==2.4.4
- numpy-quaternion==2024.0.13
- optional-django==0.3.0
- packaging==26.2
- pillow==12.2.0
- plux==1.16.0
- propcache==0.5.2
- psutil==7.2.2
- pycparser==3.0
- pydantic==2.13.4
- pydantic_core==2.46.4
- Pygments==2.20.0
- PyJWT==2.13.0
- pymongo==4.17.0
- pyotp==2.9.0
- pyquaternion==0.9.9
- python-dateutil==2.9.0.post0
- python-dotenv==1.2.2
- python-multipart==0.0.29
- pytz==2026.2
- pywin32==311
- PyYAML==6.0.3
- reportlab==4.5.1
- requests==2.34.2
- resend==2.30.1
- rich==15.0.0
- scipy==1.17.1
- semver==3.0.4
- six==1.17.0
- starlette==1.1.0
- tabulate==0.10.0
- tqdm==4.67.3
- twilio==9.10.9
- typing-inspection==0.4.2
- typing_extensions==4.15.0
- tzdata==2026.2
- tzlocal==5.3.1
- urllib3==2.7.0
- uvicorn==0.48.0
- webpack==6.0.0
- windows-curses==2.4.2
- yarl==1.24.2
- zod==0.8.0


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
cd "job-tracker/App/backend"
pip install -r requirements
uvicorn server:app --reload --port 8001
```

Terminal 2 - Frontend:

```bash
cd "job-tracker/App/frontend"
yarn install
yarn start

## Usage

1. Create or sign-in to an account.
2. Add a new job application.
3. Update the application status as the process moves forward.
4. Review saved opportunities, notes, and follow-up items.
5. Print or save PDF that adhere to IDES requirements.

## Project Structure

```job-tracker/
├── App/
    ├── .venv/
    ├── backend/
        ├── __pycache__/
        ├── assets/
        ├── tests/
        ├── .env
        ├── requirements
        ├── server.py
    ├── frontend/
        ├── src/
            ├── Pages/
                ├── Admin.jsx
                ├── AuditLog.jsx
                ├── BenefitWeeks.jsx
                ├── Calendar.jsx
                ├── Claimants.jsx
                ├── Dashboard.jsx
                ├── ForgotPassword.jsx
                ├── ImportPage.jsx
                ├── InviteSignup.jsx
                ├── Landing.jsx
                ├── Login.jsx
                ├── Profile.jsx
                ├── Register.jsx
                ├── ResetPassword.jsx
                ├── WeekDetail.jsx
        ├── components.json
        ├── craco.config.js
        ├── jsconfig.json
        ├── package.json
        ├── postcss.config.js
        ├── README.md
        ├── tailwind.config.js
        ├── yarn.lock
    ├── public/
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

