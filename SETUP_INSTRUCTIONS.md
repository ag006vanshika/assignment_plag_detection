# Plagiarism Detection Project Setup Instructions

This file explains how to set up and run the plagiarism detection system on another machine.
It includes backend and frontend installation steps, AWS configuration, and common commands.

## 1. Prerequisites

### Required software
- Git
- Python 3.10+ (3.11 recommended)
- Node.js 18+ and npm
- AWS account and AWS credentials (Access Key ID / Secret Access Key)
- Optional: AWS CLI and AWS SAM CLI for deploying AWS resources

### Recommended tools
- Visual Studio Code
- Postman or a REST API client (optional)

## 2. Clone the repository

Open a terminal or PowerShell and run:

```powershell
cd C:\Users\vansh\Desktop\aws
git clone <repository-url> assignment_plag_detection
cd assignment_plag_detection
```

Replace `<repository-url>` with the actual repository URL.

## 3. Backend setup

### 3.1 Create a Python virtual environment

```powershell
cd backend
python -m venv venv
```

### 3.2 Activate the virtual environment

- Windows:
  ```powershell
  .\venv\Scripts\activate
  ```
- macOS / Linux:
  ```bash
  source venv/bin/activate
  ```

### 3.3 Install backend dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.4 Configure environment variables

Create a copy of the example environment file:

```powershell
copy .env.example .env
```

Open `backend\.env` and set your AWS credentials and settings:

- `AWS_REGION`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`
- `DYNAMODB_TABLE_NAME`
- `FRONTEND_URL=http://localhost:3000`

Example:

```text
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY
AWS_SECRET_ACCESS_KEY=YOUR_SECRET_KEY
S3_BUCKET_NAME=plagiarism-detection-assignments
DYNAMODB_TABLE_NAME=submissions
FLASK_ENV=development
FLASK_DEBUG=true
SIMILARITY_THRESHOLD=0.60
FRONTEND_URL=http://localhost:3000
```

## 4. AWS resources setup

The backend expects:
- an S3 bucket for uploaded assignments
- a DynamoDB table for submission metadata
- optional Textract access for PDF text extraction

### Option A: Create resources manually

1. Create S3 bucket:
   - Name it the same as `S3_BUCKET_NAME`
   - Enable public access only if needed

2. Create DynamoDB table:
   - Table name: `DYNAMODB_TABLE_NAME`
   - Primary key: `PK` (string)
   - Sort key: `SK` (string)

### Option B: Use AWS CLI

If you have AWS CLI configured (`aws configure`), you can create the bucket and table manually.

### Option C: Use AWS SAM (if available)

If the project contains `backend/template.yaml`, you can deploy resources with SAM.

```powershell
cd backend
sam build
sam deploy --guided
```

Follow the prompts and make sure the bucket and table names match the `backend/.env` values.

## 5. Frontend setup

### 5.1 Install frontend dependencies

Open a second terminal and run:

```powershell
cd frontend
npm install
```

### 5.2 Start the frontend

```powershell
npm start
```

This launches the React app on `http://localhost:3000`.

## 6. Run the backend

From the backend folder with the virtual environment active:

```powershell
cd backend
.\venv\Scripts\activate
python functions/api/app.py
```

The backend API should run on `http://localhost:5000`.

## 7. Using the app

- Student upload page: `http://localhost:3000/`
- Teacher dashboard: `http://localhost:3000/dashboard`

### Upload flow
- Students upload a PDF or TXT file
- The backend uploads the file to S3
- The backend extracts text and stores submission metadata to DynamoDB
- A similarity check runs and flags suspicious submissions

### Teacher review flow
- Teachers can view the dashboard
- Click `View Details` to inspect a submission
- Use `Flag` to manually flag a submission
- Use `Mark Reviewed` to mark it as reviewed

## 8. Additional notes

- `backend/requirements.txt` contains all required Python packages
- `frontend/package.json` contains React and MUI dependencies
- `backend/.env.example` shows the required environment variables
- The app currently uses AWS Textract for PDF extraction, so valid AWS Textract permissions are required

## 9. Troubleshooting

### Backend fails to start
- Ensure the virtual environment is activated
- Verify `pip install -r requirements.txt` completed successfully
- Check `backend/.env` values and AWS credentials

### Frontend fails to start
- Ensure dependencies are installed with `npm install`
- Check for port conflicts on `3000`

### AWS errors
- Verify your AWS credentials are correct and have permissions for S3 and DynamoDB
- Confirm the S3 bucket and DynamoDB table exist and the names match `backend/.env`

## 10. Useful commands

```powershell
# Backend
cd backend
.\venv\Scripts\activate
python -m pip install -r requirements.txt
python functions/api/app.py

# Frontend
cd frontend
npm install
npm start

# AWS CLI
aws configure
```

---
