# socket_server.py
from aiohttp import web
import socketio
import json
import sqlite3
from datetime import datetime

sio = socketio.AsyncServer(cors_allowed_origins='*', logger=True, engineio_logger=True)
app = web.Application()
sio.attach(app)

# --- State Management ---
documents = {}
document_locks = {}

def get_db_conn():
    conn = sqlite3.connect('docs.db')
    return conn

def get_latest_content(doc_id):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT content FROM content WHERE doc_id = ? ORDER BY saved_at DESC LIMIT 1", (doc_id,))
    row = cur.fetchone()
    conn.close()
    return json.loads(row[0]) if row and row[0] else {"ops": []}

def save_content(doc_id, content):
    content_json = json.dumps(content)
    conn = get_db_conn()
    cur = conn.cursor()
    version = f"save_{int(datetime.now().timestamp())}"
    cur.execute("INSERT INTO content (doc_id, version, content, saved_at) VALUES (?, ?, ?, ?)", (doc_id, version, content_json, datetime.now()))
    cur.execute("UPDATE documents SET updated_at = ? WHERE id = ?", (datetime.now(), doc_id))
    conn.commit()
    conn.close()
    print(f"Saved content for {doc_id}")

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def join_document(sid, doc_id):
    await sio.enter_room(sid, doc_id)
    print(f"Client {sid} joined document {doc_id}")
    
    if doc_id not in documents:
        documents[doc_id] = get_latest_content(doc_id)
    
    await sio.emit('init', documents[doc_id], to=sid)
    
    if document_locks.get(doc_id):
        await sio.emit('lock_taken', {'by': document_locks.get(doc_id)}, to=sid)

@sio.event
async def edit(sid, data):
    doc_id = data['doc_id']
    if document_locks.get(doc_id) != sid:
        return # Reject edit if user does not have the lock
        
    await sio.emit('edit', data['operation'], room=doc_id, skip_sid=sid)
    documents[doc_id] = data['full_content'] # Update server's in-memory copy

@sio.event
async def request_lock(sid, doc_id):
    if not document_locks.get(doc_id):
        document_locks[doc_id] = sid
        print(f"Lock granted to {sid} for document {doc_id}")
        await sio.emit('lock_granted', to=sid)
        await sio.emit('lock_taken', {'by': sid}, room=doc_id, skip_sid=sid)

@sio.event
async def release_lock(sid, data):
    doc_id = data['doc_id']
    if document_locks.get(doc_id) == sid:
        document_locks[doc_id] = None
        final_content = data['full_content']
        documents[doc_id] = final_content
        save_content(doc_id, final_content)
        print(f"Lock released by {sid} for document {doc_id}")
        await sio.emit('lock_released', room=doc_id)

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
    # --- UPDATED LOGIC: Save on disconnect ---
    # Check all document locks to see if the disconnected user was editing anything.
    for doc_id, lock_sid in list(document_locks.items()):
        if lock_sid == sid:
            # The disconnected user was editing this document.
            # Get the latest content from memory and save it.
            if doc_id in documents:
                final_content = documents[doc_id]
                save_content(doc_id, final_content)
                print(f"Saved document {doc_id} on disconnect of user {sid}")

            # Now, release the lock so others can edit.
            document_locks[doc_id] = None
            print(f"Force-releasing lock for {doc_id} due to disconnect")
            await sio.emit('lock_released', room=doc_id)

if __name__ == '__main__':
    web.run_app(app, port=4000)