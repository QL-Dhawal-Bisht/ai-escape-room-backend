from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
import sys

# Add the current directory to Python path to allow app imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import your route modules
from app.routes import auth, game, tournament, user, stats
from app.database.mongodb import init_mongodb
from app.config.settings import API_TITLE, API_DESCRIPTION, API_VERSION

# Create FastAPI app instance
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION
)

# Configure CORS for frontend integration
# CORS configuration for Render + Vercel deployment
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "https://*.vercel.app",
    "https://vercel.app"
]

# Add custom origins from environment variable
custom_origins = os.getenv("ALLOWED_ORIGINS", "")
if custom_origins:
    allowed_origins.extend(custom_origins.split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now, restrict later
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Health check endpoint for cloud deployment
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring"""
    return {"status": "healthy", "service": "ai-escape-room-api"}

# Include API routers
app.include_router(auth.router)
app.include_router(game.router)
app.include_router(tournament.router)
app.include_router(user.router)
app.include_router(stats.router)

# Serve static files if ui/dist exists
ui_dist_path = os.path.join(os.path.dirname(__file__), "ui", "dist")
if os.path.exists(ui_dist_path):
    app.mount("/static", StaticFiles(directory=ui_dist_path), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Root endpoint that serves the main page or API info"""
    ui_index_path = os.path.join(os.path.dirname(__file__), "ui", "dist", "index.html")

    if os.path.exists(ui_index_path):
        # Serve the React app if built
        with open(ui_index_path, "r") as f:
            return HTMLResponse(content=f.read())
    else:
        # Serve API documentation info
        return HTMLResponse(content="""
        <html>
            <head>
                <title>AI Escape Room Game</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
                    .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                    h1 { color: #333; border-bottom: 3px solid #007acc; padding-bottom: 10px; }
                    .endpoint { background: #f8f9fa; padding: 15px; margin: 10px 0; border-left: 4px solid #007acc; border-radius: 4px; }
                    .method { color: #007acc; font-weight: bold; }
                    a { color: #007acc; text-decoration: none; }
                    a:hover { text-decoration: underline; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🎮 AI Escape Room Game API</h1>
                    <p>Welcome to the AI Escape Room Game API. This is a social engineering game with AI characters.</p>

                    <h2>📚 API Documentation</h2>
                    <p><a href="/docs">📖 Interactive API Documentation (Swagger UI)</a></p>
                    <p><a href="/redoc">📋 Alternative API Documentation (ReDoc)</a></p>

                    <h2>🔌 Available Endpoints</h2>

                    <div class="endpoint">
                        <strong class="method">POST</strong> <code>/auth/register</code> - Register a new user
                    </div>

                    <div class="endpoint">
                        <strong class="method">POST</strong> <code>/auth/login</code> - Login user
                    </div>

                    <div class="endpoint">
                        <strong class="method">POST</strong> <code>/game/start</code> - Start a new game session
                    </div>

                    <div class="endpoint">
                        <strong class="method">POST</strong> <code>/game/message</code> - Send message to game
                    </div>

                    <div class="endpoint">
                        <strong class="method">POST</strong> <code>/tournament/create</code> - Create tournament
                    </div>

                    <div class="endpoint">
                        <strong class="method">POST</strong> <code>/tournament/join</code> - Join tournament
                    </div>

                    <div class="endpoint">
                        <strong class="method">GET</strong> <code>/stats/leaderboard</code> - Get leaderboard
                    </div>

                    <h2>🚀 Getting Started</h2>
                    <ol>
                        <li>Register a new user account at <code>/auth/register</code></li>
                        <li>Login to get an access token at <code>/auth/login</code></li>
                        <li>Use the token to start playing the game at <code>/game/start</code></li>
                        <li>Join tournaments and compete with others!</li>
                    </ol>

                    <h2>🎯 Frontend</h2>
                    <p>To build and serve the React frontend:</p>
                    <pre style="background: #2d3748; color: #e2e8f0; padding: 15px; border-radius: 4px;">cd ui
npm install
npm run build</pre>
                    <p>Then restart the server to serve the built frontend.</p>
                </div>
            </body>
        </html>
        """)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "AI Escape Room Game API is running"}

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    await init_mongodb()
    print("🚀 AI Escape Room Game API is starting up...")
    print("📊 MongoDB database initialized")
    print("🌐 Server is ready to accept connections")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("🛑 AI Escape Room Game API is shutting down...")

if __name__ == "__main__":
    import uvicorn
    import os

    # Get port from environment variable (Railway sets this)
    port = int(os.getenv("PORT", 8000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # Disable reload in production
        log_level="info"
    )
