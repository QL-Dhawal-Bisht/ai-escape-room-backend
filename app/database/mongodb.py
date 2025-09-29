import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# MongoDB connection string
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb+srv://dhawalbisht4543_db_user:YzfJGiwpPp4ebsPQ@cluster0.dtpwdma.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
DATABASE_NAME = "ai_escape_room"

# Global client instance
_client: Optional[AsyncIOMotorClient] = None
_db = None

def get_database():
    """Get MongoDB database instance"""
    global _client, _db

    if _client is None:
        _client = AsyncIOMotorClient(MONGODB_URL)
        _db = _client[DATABASE_NAME]

    return _db

async def init_mongodb():
    """Initialize MongoDB collections and indexes"""
    try:
        db = get_database()

        # Create collections if they don't exist
        collections = await db.list_collection_names()

        required_collections = [
            "users",
            "game_sessions",
            "game_results",
            "tournaments",
            "tournament_participants",
            "tournament_game_sessions",
            "tournament_events",
            "prompt_exploitation_history"
        ]

        for collection_name in required_collections:
            if collection_name not in collections:
                await db.create_collection(collection_name)
                logger.info(f"Created collection: {collection_name}")

        # Create indexes for better performance
        await create_indexes(db)

        logger.info("MongoDB database initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Error initializing MongoDB: {e}")
        raise

async def create_indexes(db):
    """Create database indexes for better performance"""
    try:
        # Users collection indexes
        await db.users.create_index("username", unique=True)
        await db.users.create_index("email", unique=True)

        # Game sessions indexes
        await db.game_sessions.create_index([("user_id", 1), ("created_at", -1)])
        await db.game_sessions.create_index("game_over")

        # Game results indexes
        await db.game_results.create_index([("user_id", 1), ("completed_at", -1)])
        await db.game_results.create_index([("final_score", -1)])

        # Tournament indexes
        await db.tournaments.create_index("room_code", unique=True)
        await db.tournaments.create_index([("status", 1), ("created_at", -1)])

        # Exploitation history indexes
        await db.prompt_exploitation_history.create_index([("user_id", 1), ("created_at", -1)])
        await db.prompt_exploitation_history.create_index([("stage", 1)])

        logger.info("Database indexes created successfully")

    except Exception as e:
        logger.error(f"Error creating indexes: {e}")

# Synchronous wrapper for compatibility
def get_db():
    """Synchronous database access for backward compatibility"""
    return MongoDBSync()

class MongoDBSync:
    """Synchronous wrapper for MongoDB operations"""

    def __init__(self):
        self.client = MongoClient(MONGODB_URL)
        self.db = self.client[DATABASE_NAME]

    def cursor(self):
        return MongoDBCursor(self.db)

    def close(self):
        self.client.close()

    def commit(self):
        # MongoDB auto-commits, so this is a no-op for compatibility
        pass

    def execute(self, query: str, params=None):
        # This is for compatibility with SQL-like calls
        return MongoDBCursor(self.db)

class MongoDBCursor:
    """Cursor wrapper for MongoDB operations"""

    def __init__(self, db):
        self.db = db
        self.results = []

    def execute(self, query: str, params=None):
        # This would need to be implemented based on specific SQL queries
        # For now, this is just a placeholder for compatibility
        pass

    def fetchone(self):
        return self.results[0] if self.results else None

    def fetchall(self):
        return self.results

async def test_connection():
    """Test MongoDB connection"""
    try:
        client = AsyncIOMotorClient(MONGODB_URL)
        # Ping the database
        await client.admin.command('ping')
        client.close()
        logger.info("MongoDB connection successful")
        return True
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        return False

# Helper functions for common operations
async def create_user(user_data: Dict[str, Any]) -> str:
    """Create a new user"""
    db = get_database()
    user_data["created_at"] = datetime.utcnow()
    result = await db.users.insert_one(user_data)
    return str(result.inserted_id)

async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get user by username"""
    db = get_database()
    user = await db.users.find_one({"username": username})
    if user:
        user["id"] = str(user["_id"])  # Convert ObjectId to string
    return user

async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email"""
    db = get_database()
    user = await db.users.find_one({"email": email})
    if user:
        user["id"] = str(user["_id"])
    return user

async def create_game_session(session_data: Dict[str, Any]) -> str:
    """Create a new game session"""
    db = get_database()
    session_data["created_at"] = datetime.utcnow()
    session_data["updated_at"] = datetime.utcnow()
    result = await db.game_sessions.insert_one(session_data)
    return str(result.inserted_id)

async def get_game_session(session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Get game session by ID and user ID"""
    db = get_database()
    session = await db.game_sessions.find_one({"id": session_id, "user_id": user_id})
    return session

async def update_game_session(session_id: str, update_data: Dict[str, Any]):
    """Update game session"""
    db = get_database()
    update_data["updated_at"] = datetime.utcnow()
    await db.game_sessions.update_one(
        {"id": session_id},
        {"$set": update_data}
    )