
# HQ-Oversight: Combined Mathematics Evaluation Engine (Backend)

The core high-performance REST API engine powering the HQ-Oversight automated ecosystem. Engineered with a highly decoupled, asynchronous architecture, this backend coordinates secure student authentication, handles transactional SMTP mail loops, manages multi-part file payloads, and processes complex relational analytical pipelines for student performance matrices.

🖥️ **Frontend Repository:** [github.com/udara-lakshitha/hq-oversight-frontend](https://github.com/udara-lakshitha/hq-oversight-frontend)  
🔗 **Live Application:** [hqmaths.netlify.app](https://hqmaths.netlify.app/)

---

## 🚀 Architectural Blueprint & Systems Design

The backend is architected as an asynchronous ASGI service optimized for IO-bound operations, data integrity, and strict access controls.

* **Framework Layer:** FastAPI (Python 3.10+) utilizing structural Type Hinting and Pydantic v2 data validation schemas.
* **Database Infrastructure:** PostgreSQL object-relational database.
* **Data Access Layer:** SQLAlchemy 2.0 ORM configured with an asynchronous execution abstraction layer.

---

## 🛠️ Technical Stack & Production Tooling

* **Web Framework:** FastAPI / Uvicorn (ASGI web server implementation)
* **Database & Migration Engine:** PostgreSQL / Alembic (Handles programmatic DB versioning and schema evolutions)
* **Security & Crypto Layer:** Passlib (Bcrypt hashing mechanics) / PyJWT (JSON Web Token state management)
* **Mail Transmission Pipeline:** Resend SMTP client integration (Handles transactional security loops)
* **File Processing:** Python-Multipart / Shutil system streams (Engineered for secure, buffered question paper PDF uploads)

---

## 💎 Core Backend Engineering Milestones

### 1. Robust CORS Middleware & Route Preflight Integrity
The API engine implements strict Cross-Origin Resource Sharing protocols. By removing terminal slash anomalies systematically across explicit, production-grade origin registries, it completely bypasses routing conflicts (`400 Bad Request`) during complex preflight browser transactions:

### 2. Resilient Database Connection Pooling
To mitigate infrastructure dropped links and prevent connection starvation over shared public container environments, the engine incorporates connection polling protections and proactive health checks:

* pool_recycle=1800: Systematically discards and recreates stale db connections older than 30 minutes.
* pool_pre_ping=True: Executes an efficient testing statement immediately before allocating any connection pool member, completely eliminating transactional query faults if a database server times out.

### 3. Granular Cryptographic Security Lifecycle
* **Transient Session Passkeys:** Implements an automated authentication flow generating short-lived, self-destructing random passkeys transmitted through the Resend mail API for identity validation checks.
* **Role-Based Access Delegation:** Utilizes layered FastAPI dependency injections (Depends()) to partition student testing paths away from managerial dashboard actions (/api/exams/stream-paper).

## 📡 Core API Endpoint Specification Matrix

| Endpoint Router | HTTP Method | Access Level | Functional Operational Description |
| :--- | :---: | :---: | :--- |
| `/auth/login` | `POST` | Public | Validates credentials, issues secure JWT access tokens. |
| `/auth/verify-passkey` | `POST` | Public | Processes temporary cryptographic verification keys. |
| `/students/` | `POST` | Public | Direct payload parsing and schema registration validation. |
| `/api/exams/stream-paper/{id}` | `GET` | Authenticated | Streams structural testing PDF binaries directly across network boundaries. |
| `/api/admin/upload-paper` | `POST` | Administrator | Processes multi-part document pipelines into cloud database records. |
| `/api/admin/marks-ledger` | `GET` | Administrator | Computes global multi-parametric student evaluation matrices. |

## 🛠️ Local Backend Deployment Guide

### 1. Clone the repository workspace:
```bash
git clone [https://github.com/udara-lakshitha/hq-oversight-backend.git](https://github.com/udara-lakshitha/hq-oversight-backend.git)
cd hq-oversight-backend
```

### 2. Configure isolated python runtime virtual environments:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

### 3. Install requirements using the python package dependency manager:
```bash
pip install -r requirements.txt
```

### 4. Populate your local environment infrastructure variables (.env):
```bash
DATABASE_URL=postgresql://postgres:secret@localhost:5432/hq_oversight
SECRET_KEY=your_cryptographic_jwt_signing_key_string
RESEND_API_KEY=re_your_resend_smtp_integration_token
```

### 5. Fire up the high-performance local server:
```bash
uvicorn app.main:app --reload --port 8000 
```
