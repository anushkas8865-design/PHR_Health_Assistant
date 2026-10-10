
# Intelligent Personal Health Record (PHR) Assistant

A web-based health information and personal health record application developed using Python and Flask. The application provides medical question answering using a cleaned medical information dataset and includes features for recording health observations, reviewing health history, viewing health summaries, and accessing medication schedules and reminders.

## Project Links

- **Live Application:** https://phr-health-assistant.onrender.com
- **Source Code Repository:** https://github.com/anushkas8865-design/PHR_Health_Assistant

## 1. Project Overview

The Intelligent Personal Health Record (PHR) Assistant is designed to provide users with an accessible web interface for health-related information and personal health record management.

The application allows users to submit health-related questions and receive responses through its medical question-answering functionality. It also provides interfaces for entering personal health information, recording symptom observations, reviewing health history, viewing a factual health summary, and accessing medication schedules and reminders.

The application is developed using Python and Flask. Its medical question-answering functionality uses a cleaned dataset named `medquad_clean.json`, stored in the project's `data` directory.

The application has been deployed on Render and is accessible through a public web URL.

## 2. Project Objectives

The main objectives of the project are:

- To provide a web-based interface for asking health-related questions.
- To use a cleaned medical information dataset to support question answering.
- To provide an interface for entering personal health information and symptom observations.
- To allow users to review available health history and health summaries.
- To provide access to medication schedules and reminder-related features.
- To deploy the application online so that it can be accessed through a web browser.

## 3. Features

### 3.1 Medical Q&A

The Medical Q&A page allows users to submit health-related questions and receive responses from the application's question-answering functionality.

The application uses the cleaned medical information dataset, `data/medquad_clean.json`, to support this functionality.

Example test question:

"What are the common symptoms of asthma?"

The response depends on the information available in the dataset and the application's implemented question-answering process.

### 3.2 Personal Health Record Entry

The application provides a health record entry interface for entering personal health information.

The record-entry form includes fields such as:

- Title / Summary
- Metric Name
- Value
- Unit
- Details & Notes (Optional)

These fields can be used to demonstrate the entry of health measurements and related notes.

### 3.3 Symptom Observation

The personal health entry functionality can be used to record symptom observations. Users can enter the available information and submit it through the application's record-entry interface.

### 3.4 Health History

The Health History page provides an interface for reviewing health information recorded in the application.

It can be used to check whether previously entered health information is displayed in the history.

### 3.5 Factual Health Summary

The Factual Health Summary page presents available health information in a consolidated format, making the information easier to review.

The information displayed depends on the data and summary functionality implemented in the application.

### 3.6 Medication Schedules & Reminders

The Medication Schedules & Reminders page provides an interface for accessing medication scheduling and reminder-related information.

The application also provides a way to check medication-related notifications through its interface.

## 4. Technologies Used

| Technology | Purpose |
|---|---|
| Python | Programming language used for the application backend. |
| Flask | Web framework used to develop the web application. |
| JSON | Data format used for the cleaned medical information dataset. |
| Gunicorn | WSGI application server used to run the application in the deployed environment. |
| Render | Cloud platform used to host the application. |
| PowerShell | Command-line environment used for project setup and deployment preparation on Windows. |

## 5. Medical Information Dataset

The project uses a cleaned medical information dataset stored at:

`data/medquad_clean.json`

The dataset is maintained in JSON format and is used to support the medical question-answering functionality.

The cleaned dataset is included in the project so that it is available to the application in the deployed environment.

## 6. Project Structure

The confirmed main project files include:

```text
PHR_Health_Assistant/
├── app.py
├── requirements.txt
└── data/
    └── medquad_clean.json
```

The project may contain additional files and directories supporting the web interface, application functionality, and tests.

### Main Files

**`app.py`**

Contains the Flask application implementation and the `create_app()` application factory.

**`requirements.txt`**

Lists the Python packages required by the application. Render uses this file to install dependencies during deployment.

**`data/medquad_clean.json`**

Contains the cleaned medical information dataset used to support health question answering.

## 7. Application Architecture

The application follows a Flask-based web application structure.

The high-level flow is:

1. The user opens the application through a web browser.
2. The user accesses a feature, such as Medical Q&A or personal health record entry.
3. The Flask application handles the relevant request using its implemented functionality.
4. For medical questions, the application uses its question-answering functionality and cleaned medical information dataset.
5. The application presents the resulting response or available health information through its interface.

The application is deployed using Gunicorn on Render.

## 8. Installation and Local Setup

### Prerequisites

- Python
- pip
- A local copy of the project repository

### Step 1: Obtain the project

Clone the project repository:

```bash
git clone https://github.com/anushkas8865-design/PHR_Health_Assistant.git
```

Navigate to the project directory:

```bash
cd PHR_Health_Assistant
```

### Step 2: Create a virtual environment

On Windows, run:

```powershell
python -m venv .venv
```

Activate the environment:

```powershell
.venv\Scripts\Activate.ps1
```

### Step 3: Install dependencies

Install the packages listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

### Step 4: Run the application

The Flask application uses the `create_app()` application factory defined in `app.py`.

The configured Gunicorn command is:

```bash
gunicorn "app:create_app()"
```

This is the command used in the Render deployment configuration. Local execution should be performed in an environment where Gunicorn is available and supported.

## 9. Deployment on Render

The application has been deployed on Render.

The deployment configuration uses the following commands.

**Build Command**

```bash
pip install -r requirements.txt
```

**Start Command**

```bash
gunicorn "app:create_app()"
```

### Deployment Configuration

| Configuration | Value |
|---|---|
| Project Name | PHR Health Assistant |
| Programming Language | Python |
| Web Framework | Flask |
| Application Entry File | `app.py` |
| Application Factory | `create_app()` |
| Application Server | Gunicorn |
| Dataset File | `data/medquad_clean.json` |
| Hosting Platform | Render |
| Deployment Status | Live |

### Live Application

The deployed application is available at:

https://phr-health-assistant.onrender.com

The homepage and medical question-answering functionality have been tested and confirmed to work in the deployed environment.

## 10. Testing

The following tests have been performed or explored during project verification.

| Test Case | Test Description | Status |
|---|---|---|
| TC01 | Open the deployed application homepage. | Passed |
| TC02 | Submit a health-related question through Medical Q&A. | Passed |
| TC03 | Test the question "What are the common symptoms of asthma?" | Use the observed result when documenting this specific test. |
| TC04 | Enter a sample health measurement through the record-entry form. | Test through the running application. |
| TC05 | Submit a symptom observation and check whether it is saved. | Verify the actual result. |
| TC06 | Check the Health History page for the recorded entry. | Verify the actual result. |
| TC07 | Review the Factual Health Summary page. | Verify the displayed information. |
| TC08 | Open Medication Schedules & Reminders and check the notification interface. | Verify the actual result. |

Only mark a test as passed when its result has been observed in the running application.

## 11. Results

The application was successfully deployed to Render. The homepage loads correctly, and the medical question-answering functionality has been tested and confirmed to work.

The deployed application provides access to its health-related question-answering and personal health record interfaces. The individual record-saving, history, summary, and medication notification behaviours should be documented according to their observed results during testing.

## 12. Privacy and Medical Disclaimer

Use fictional test information when demonstrating the application.

Before entering real patient information, ensure that appropriate privacy protections, access controls, and reliable data storage are in place.

The application provides health information for informational purposes only. It is not a substitute for professional medical advice, diagnosis, or treatment.

## 13. Future Scope

Potential areas for further improvement include:

- Improving the relevance of answers to health-related questions.
- Verifying reliable persistence of personal health records.
- Strengthening privacy and security protections before using real patient data.
- Testing record saving and retrieval across application restarts.
- Verifying the behaviour of medication schedules and notifications.

These are potential improvements and are not presented as features already implemented.

## 14. Conclusion

The Intelligent Personal Health Record Assistant demonstrates the development and deployment of a web-based health application using Python and Flask.

The application combines medical question answering supported by a cleaned JSON dataset with interfaces for personal health record entry, symptom observation, health history, factual health summaries, and medication schedules and reminders.

The application is live on Render, and its homepage and medical question-answering functionality have been verified.

## 15. Project Links

- **GitHub Repository:** https://github.com/anushkas8865-design/PHR_Health_Assistant
- **Live Application:** https://phr-health-assistant.onrender.com
```
