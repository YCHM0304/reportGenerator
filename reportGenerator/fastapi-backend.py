from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uuid
import os
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("api.log")
    ]
)
logger = logging.getLogger(__name__)

# Models for our API
class Message(BaseModel):
    role: str  # "user" or "agent"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)

class Source(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str  # "file" or "url"
    content: str
    file_path: Optional[str] = None  # 存儲完整檔案路徑，僅用於檔案類型
    selected: bool = True
    created_at: datetime = Field(default_factory=datetime.now)

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

class PreviewResponse(BaseModel):
    preview: str

class SessionData(BaseModel):
    session_id: str
    messages: List[Message] = []
    sources: List[Source] = []
    preview: str = "這裡將顯示報告預覽..."
    created_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)

# In-memory storage for sessions (in a production environment, use a database)
sessions = {}

# Clean up old sessions periodically
def cleanup_old_sessions():
    cutoff_time = datetime.now() - timedelta(hours=24)  # Sessions older than 24 hours
    expired_sessions = [s_id for s_id, session in sessions.items() if session.last_activity < cutoff_time]

    for s_id in expired_sessions:
        del sessions[s_id]

    if expired_sessions:
        logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

app = FastAPI(title="Report Generator API")

# Add CORS middleware to allow Streamlit to communicate with our API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your Streamlit app's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper function to get or create a session
def get_or_create_session(session_id: Optional[str] = Header(None, convert_underscores=False)) -> SessionData:
    if not session_id:
        # Generate a new session ID if not provided
        session_id = str(uuid.uuid4())
        sessions[session_id] = SessionData(session_id=session_id)
        logger.info(f"Created new session: {session_id}")
    elif session_id not in sessions:
        # Create a new session with the provided ID
        sessions[session_id] = SessionData(session_id=session_id)
        logger.info(f"Created new session with provided ID: {session_id}")
    else:
        # Update last activity timestamp
        sessions[session_id].last_activity = datetime.now()

    return sessions[session_id]

# Agent class to handle responses
class Agent:
    @staticmethod
    def respond(message: str, sources: List[Source]) -> str:
        # Here you would implement your actual agent logic
        # This is a placeholder
        active_sources = [s for s in sources if s.selected]
        sources_text = ", ".join([f"{s.type}: {s.content}" for s in active_sources])

        if active_sources:
            return f"Agent回應: 基於{sources_text}的參考，我對於「{message}」的回應是..."
        else:
            return f"Agent回應: {message}"

    @staticmethod
    def generate_preview(messages: List[Message], sources: List[Source]) -> str:
        # Generate a report preview based on the conversation and sources
        # This is a placeholder
        active_sources = [s for s in sources if s.selected]

        if not messages:
            return "這裡將顯示報告預覽..."

        preview = "根據討論生成的報告預覽...\n\n"

        # Add a summary of the conversation
        user_messages = [m for m in messages if m.role == "user"]

        if user_messages:
            latest_message = user_messages[-1].content
            preview += f"主題: {latest_message}\n\n"

        # Add sources used
        if active_sources:
            preview += "參考資料:\n"
            for s in active_sources:
                preview += f"- {s.type}: {s.content}\n"

        return preview

# API Endpoints

@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    session: SessionData = Depends(get_or_create_session)
):
    # Schedule cleanup of old sessions
    background_tasks.add_task(cleanup_old_sessions)

    # Add user message to history
    user_message = Message(role="user", content=request.message)
    session.messages.append(user_message)
    logger.info(f"Session {session.session_id}: Received user message")

    try:
        # Generate agent response using the Agent class
        agent_response = Agent.respond(request.message, session.sources)

        # Add agent message to history
        agent_message = Message(role="agent", content=agent_response)
        session.messages.append(agent_message)

        # Update preview
        session.preview = Agent.generate_preview(session.messages, session.sources)

        # Update last activity timestamp
        session.last_activity = datetime.now()

        return ChatResponse(response=agent_response, session_id=session.session_id)

    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.post("/sources", response_model=Source)
async def add_source(
    source_type: str = Form(...),
    content: str = Form(...),
    file: Optional[UploadFile] = None,
    session: SessionData = Depends(get_or_create_session)
):
    try:
        if source_type == "file" and file:
            # Create uploads directory if it doesn't exist
            os.makedirs("uploads", exist_ok=True)

            # 使用session_id作為前綴，確保檔案與會話關聯
            unique_filename = f"{session.session_id}_{file.filename}"
            file_location = f"uploads/{unique_filename}"

            # Save the file
            with open(file_location, "wb") as f:
                contents = await file.read()
                f.write(contents)

            # 存儲完整檔名以便於刪除時精確匹配
            new_source = Source(type="file", content=file.filename, file_path=unique_filename)

        elif source_type == "url":
            # Validate URL (basic validation)
            if not content.startswith(("http://", "https://")):
                raise HTTPException(status_code=400, detail="Invalid URL format")

            new_source = Source(type="url", content=content)

        else:
            raise HTTPException(status_code=400, detail="Invalid source type or missing required data")

        # Add source to session
        session.sources.append(new_source)

        # Update preview
        session.preview = Agent.generate_preview(session.messages, session.sources)

        # Update last activity timestamp
        session.last_activity = datetime.now()

        logger.info(f"Session {session.session_id}: Added new source - {source_type}")
        return new_source

    except Exception as e:
        logger.error(f"Error adding source: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error adding source: {str(e)}")

@app.put("/sources/{source_id}", response_model=Source)
async def toggle_source(
    source_id: str,
    selected: bool,
    session: SessionData = Depends(get_or_create_session)
):
    for source in session.sources:
        if source.id == source_id:
            source.selected = selected

            # Update preview after toggling source
            session.preview = Agent.generate_preview(session.messages, session.sources)

            # Update last activity timestamp
            session.last_activity = datetime.now()

            logger.info(f"Session {session.session_id}: Toggled source {source_id} to {selected}")
            return source

    logger.warning(f"Session {session.session_id}: Source {source_id} not found")
    raise HTTPException(status_code=404, detail="Source not found")

@app.delete("/sources/{source_id}")
async def remove_source(
    source_id: str,
    session: SessionData = Depends(get_or_create_session)
):
    for i, source in enumerate(session.sources):
        if source.id == source_id:
            # Remove the source
            removed_source = session.sources.pop(i)

            # If it's a file, delete the file from disk
            if removed_source.type == "file":
                try:
                    # 構建精確的檔案名，使用session_id確保只刪除當前會話的檔案
                    file_name = f"{session.session_id}_{removed_source.content}"
                    file_path = os.path.join("uploads", file_name)

                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Deleted file: {file_path}")
                except Exception as e:
                    logger.error(f"Error deleting file: {str(e)}")

            # Update preview after removing source
            session.preview = Agent.generate_preview(session.messages, session.sources)

            # Update last activity timestamp
            session.last_activity = datetime.now()

            logger.info(f"Session {session.session_id}: Removed source {source_id}")
            return {"detail": "Source removed successfully"}

    logger.warning(f"Session {session.session_id}: Source {source_id} not found for removal")
    raise HTTPException(status_code=404, detail="Source not found")

@app.get("/preview", response_model=PreviewResponse)
async def get_preview(session: SessionData = Depends(get_or_create_session)):
    # Update last activity timestamp
    session.last_activity = datetime.now()
    return PreviewResponse(preview=session.preview)

@app.get("/messages")
async def get_messages(session: SessionData = Depends(get_or_create_session)):
    # Update last activity timestamp
    session.last_activity = datetime.now()
    return {"messages": session.messages}

@app.get("/sources")
async def get_sources(session: SessionData = Depends(get_or_create_session)):
    # Update last activity timestamp
    session.last_activity = datetime.now()
    return {"sources": session.sources}

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "sessions_count": len(sessions)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
