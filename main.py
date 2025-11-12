import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import ChatRoom, ChatMessage

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RoomCreate(BaseModel):
    name: str

class MessageCreate(BaseModel):
    room_id: str
    username: str
    content: str


def to_str_id(doc: dict):
    if doc is None:
        return None
    d = {**doc}
    if "_id" in d:
        d["_id"] = str(d["_id"])
    return d


@app.get("/")
def read_root():
    return {"message": "Anonymous Chat API is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Rooms
@app.post("/api/rooms")
def create_room(payload: RoomCreate):
    room = ChatRoom(name=payload.name)
    room_id = create_document("chatroom", room)
    return {"id": room_id, "name": room.name}

@app.get("/api/rooms")
def list_rooms():
    rooms = get_documents("chatroom")
    return [{"id": str(r["_id"]), "name": r.get("name", "Room") } for r in rooms]


# Messages
@app.post("/api/messages")
def send_message(payload: MessageCreate):
    # basic room existence check
    try:
        _id = ObjectId(payload.room_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid room id")

    room = db["chatroom"].find_one({"_id": _id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    msg = ChatMessage(room_id=payload.room_id, username=payload.username, content=payload.content)
    msg_id = create_document("chatmessage", msg)
    return {"id": msg_id}

@app.get("/api/messages")
def get_messages(room_id: str, limit: int = 50):
    try:
        _id = ObjectId(room_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid room id")

    cursor = db["chatmessage"].find({"room_id": room_id}).sort("created_at", -1).limit(limit)
    messages = list(cursor)[::-1]
    return [
        {
            "id": str(m["_id"]),
            "room_id": m.get("room_id"),
            "username": m.get("username"),
            "content": m.get("content"),
            "created_at": m.get("created_at")
        }
        for m in messages
    ]


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
