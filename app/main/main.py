from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.main.database import engine, Base
from app.main.routers import students
from app.main.routers import auth

# Generate the physical SQLite database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="HQ-Oversight Academic Evaluation Engine")

# Explicitly allow your modern Vite frontend port configuration layout
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the core functional sub-system routers
app.include_router(students.router)
app.include_router(auth.router)

@app.get("/")
def root_status_check():
    return {"status": "online", "system": "HQ-Oversight Backend Engine"}