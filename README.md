# 🌱 EcoPilot AI – Unified Green Platform

EcoPilot AI is a state-of-the-art carbon footprint tracking, analytics, and lifestyle-coaching web application. It empowers users to monitor their carbon impact, scan utility statements, perform visual appliance audits, run carbon simulations, and receive personalized recommendations backed by AI.

---

## 🌟 Architecture Breakdown

The project is structured into three clean services for maximum modularity and scalability:
1.  **Frontend** (`frontend/`): A standard Single Page Application (SPA) built using **React + Vite** and JavaScript. Preserves the visual aesthetics of the original platform, using Tailwind CSS and Framer Motion, and connects to the Node.js backend.
2.  **Backend** (`backend/`): A **Node.js + Express.js** server serving user authentication, daily logging, Mongoose models, and orchestrating API calls. Persists all records directly to **MongoDB**.
3.  **Client / AI Microservice** (`client/`): A stateless **Python FastAPI** service hosting AI functionality (Google Gemini API, OCR pipelines, and XGBoost carbon footprint predictors). Serves requests over HTTP without direct database access.

```
                     ┌──────────────────────────┐
                     │       User Browser       │
                     └─────────────┬────────────┘
                                   │
                                   ▼ HTTP / JSON
                     ┌──────────────────────────┐
                     │   frontend (Port 3000)   │
                     │       Vite + React       │
                     └─────────────┬────────────┘
                                   │
                                   ▼ API requests
                     ┌──────────────────────────┐
                     │   backend (Port 8000)    │     Mongoose
                     │     Node.js Express      ├───────────────┐
                     └─────────────┬────────────┘               │
                                   │                            ▼
                    AI requests    ▼                     ┌─────────────┐
                     ┌──────────────────────────┐        │   MongoDB   │
                     │    client (Port 8001)    │        │(Port 27017) │
                     │   FastAPI / Gemini / ML  │        └─────────────┘
                     └──────────────────────────┘
```

---

## 🛠️ Technology Stack

### Frontend
-   **Framework**: React 19 + Vite 8 (JavaScript SPA)
-   **Styling**: Tailwind CSS + Custom Dark Mode themes
-   **Animations**: Framer Motion
-   **Routing**: React Router DOM v7
-   **Icons**: Lucide React
-   **Charts**: Recharts & Custom SVGs

### Backend (Express)
-   **Framework**: Node.js + Express.js
-   **Database**: MongoDB via Mongoose
-   **Security**: jsonwebtoken (JWT) & bcryptjs (Password hashing)
-   **Services**: pdfkit (sustainability reports) & nodemailer (notifications)

### Client (Python AI)
-   **Framework**: FastAPI + Uvicorn
-   **AI/LLM**: Google GenAI SDK (utilizing `gemini-2.5-flash`)
-   **OCR**: pytesseract, pypdf, and google-cloud-vision
-   **Machine Learning**: Scikit-Learn & XGBoost (for carbon simulation forecasting)

---

## 📁 Project Directory Structure

```
├── backend/                    # Node.js Express server
│   ├── config/                 # MongoDB database client settings
│   ├── controllers/            # API request controller logic
│   ├── middleware/             # JWT auth & security filters
│   ├── models/                 # Mongoose database schemas
│   ├── routes/                 # Express endpoint router definitions
│   ├── services/               # PDF report and email helpers
│   ├── server.js               # Server entry point
│   ├── package.json            # Node.js dependencies
│   └── .env                    # Environment settings
├── client/                     # Stateless Python FastAPI microservice
│   ├── ai/                     # Gemini prompt logic
│   ├── api/                    # FastAPI endpoints (ai_endpoints.py)
│   ├── core/                   # Configuration settings (settings.py)
│   ├── middleware/             # Security headers filters
│   ├── ml/                     # ML training logic
│   ├── models/                 # ML serialized model (.pkl files)
│   ├── ocr/                    # OCR Vision analysis helpers
│   ├── services/               # Business analysis services
│   ├── main.py                 # FastAPI microservice entry point
│   ├── requirements.txt        # Python dependency manifest
│   └── .env                    # Environment settings
├── frontend/                   # Vite React frontend application
│   ├── public/                 # Static assets (images, icons)
│   ├── src/
│   │   ├── assets/             # Images & static assets
│   │   ├── components/         # Reusable layouts & UI widgets
│   │   ├── pages/              # SPA page components
│   │   ├── services/           # API fetch and token client
│   │   ├── App.jsx             # React Router routing map
│   │   ├── index.css           # Global Tailwind CSS style template
│   │   └── main.jsx            # React root injection point
│   ├── vite.config.js          # Vite config server settings
│   └── package.json            # Frontend dependencies
├── docker-compose.yml          # Container configuration for local stack
└── README.md                   # Project documentation
```

---

## ⚙️ Configuration & Environment Setup

### 1. Express Backend Setup (`backend/.env`)
Create a `.env` file inside the `backend/` folder:
```env
MONGODB_URI=mongodb://127.0.0.1:27017/ecopilot
JWT_SECRET=supersecretjwtkeythatisreallylongandsecure123!
ACCESS_TOKEN_EXPIRE_MINUTES=1440
AI_SERVICE_URL=http://127.0.0.1:8001
ENVIRONMENT=development
PORT=8000
```

### 2. Python Client Setup (`client/.env`)
Create a `.env` file inside the `client/` folder:
```env
MONGODB_URI=mongodb://localhost:27017/ecopilot
JWT_SECRET=supersecretjwtkeythatisreallylongandsecure123!
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
GEMINI_API_KEY=your_gemini_api_key_here
NEXT_PUBLIC_API_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
GOOGLE_APPLICATION_CREDENTIALS=dummy_path.json
ENVIRONMENT=development
```

### 3. Frontend Setup
Vite resolves local API configurations using `import.meta.env.VITE_API_URL`. It defaults to `http://127.0.0.1:8000` (Node.js backend port), but can be customized by defining a `VITE_API_URL` variable.

---

## 🚀 Running the Project Locally

### Option A: Docker Compose (All-in-One)
To run the full stack (database, microservice, server, and React UI) in containerized environments:
```bash
docker-compose up --build
```
*   **Vite Frontend:** `http://localhost:3000`
*   **Express Backend:** `http://localhost:8000`
*   **FastAPI AI Client:** `http://localhost:8001`
*   **MongoDB:** `mongodb://localhost:27017`

### Option B: Manual Setup (Development)

1.  **MongoDB**: Start your local MongoDB service listening on Port `27017`.
2.  **Stateless AI Microservice**:
    
    **Windows**:
    ```powershell
    cd client
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn main:app --port 8001 --reload
    ```
    
    **Unix / macOS**:
    ```bash
    cd client
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    uvicorn main:app --port 8001 --reload
    ```
3.  **Express Backend**:
    ```bash
    cd backend
    npm install
    npm start
    ```
4.  **Vite React Frontend**:
    ```bash
    cd frontend
    npm install
    npm run dev
    ```
