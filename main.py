# main.py
from fastapi import FastAPI, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import sqlite3
import json
from datetime import datetime, timedelta, timezone
import time
import uuid

# --- Authentication Imports ---
from passlib.context import CryptContext
from jose import JWTError, jwt
from typing import Optional

# --- App and Template Setup ---
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- Authentication Configuration ---
SECRET_KEY = "a_very_secret_key_change_this_in_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Pydantic Models ---
class Document(BaseModel):
    title: str

class User(BaseModel):
    username: str

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# --- Database Connection ---
def get_db_conn():
    conn = sqlite3.connect('docs.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- Password and Token Utilities ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Dependency to get current user ---
async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None

# === HTML Page Routes ===

@app.get("/", response_class=HTMLResponse)
async def route_root(username: str = Depends(get_current_user)):
    if username:
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, username: str = Depends(get_current_user)):
    if not username:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("dashboard.html", {"request": request, "username": username})

@app.get("/documents/{doc_id}", response_class=HTMLResponse)
async def render_editor(request: Request, doc_id: str, username: str = Depends(get_current_user)):
    if not username:
        return RedirectResponse(url="/login")
    # You might want to add a check here to ensure the user has permission to view this doc
    return templates.TemplateResponse("editor.html", {"request": request, "doc_id": doc_id})

# === API Routes ===

@app.post("/api/signup")
async def api_signup(username: str = Form(...), password: str = Form(...)):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    if cur.fetchone():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(password)
    cur.execute("INSERT INTO users (username, hashed_password) VALUES (?, ?)", (username, hashed_password))
    conn.commit()
    conn.close()
    return {"message": "User created successfully"}

@app.post("/api/login", response_class=HTMLResponse)
async def api_login(username: str = Form(...), password: str = Form(...)):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cur.fetchone()
    conn.close()
    if not user or not verify_password(password, user['hashed_password']):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": username})
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response

@app.post("/api/logout", response_class=HTMLResponse)
async def api_logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

@app.get("/api/documents")
async def get_documents(username: str = Depends(get_current_user)):
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, title, updated_at FROM documents WHERE owner_id = ? ORDER BY updated_at DESC", (username,))
    docs = cur.fetchall()
    conn.close()
    return docs

@app.post("/api/documents")
async def create_document(doc: Document, username: str = Depends(get_current_user)):
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    doc_id = "doc_" + str(uuid.uuid4())
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO documents (id, title, owner_id) VALUES (?, ?, ?)",
        (doc_id, doc.title, username)
    )
    # Create initial empty content
    initial_content = json.dumps({"ops": []})
    cur.execute(
        "INSERT INTO content (doc_id, version, content) VALUES (?, ?, ?)",
        (doc_id, f"v_{int(time.time())}", initial_content)
    )
    conn.commit()
    conn.close()
    return {"id": doc_id, "title": doc.title}

@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: str, username: str = Depends(get_current_user)):
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT owner_id FROM documents WHERE id = ?", (doc_id,))
    doc = cur.fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc['owner_id'] != username:
        raise HTTPException(status_code=403, detail="Not authorized to delete this document")
    
    # ON DELETE CASCADE in db.py handles deleting content rows
    cur.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    return {"message": "Document deleted"}