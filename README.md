# 🎮 AI Escape Room - Backend API

FastAPI backend for the AI Escape Room game with MongoDB Atlas integration.

## 🚀 Features

- **FastAPI** REST API with automatic documentation
- **MongoDB Atlas** cloud database
- **JWT Authentication** with secure user management
- **Game Logic** for 5 AI character stages
- **Tournament System** for competitive play
- **Security Logging** tracks exploitation attempts
- **Adaptive Difficulty** learns from user behavior

## 🏗️ Architecture

```
FastAPI Backend
├── Authentication & User Management
├── Game Engine & AI Characters
├── Tournament System
├── Leaderboards & Statistics
├── Security & Monitoring
└── MongoDB Data Layer
```

## 🛠️ Tech Stack

- **Framework**: FastAPI 0.104.1
- **Database**: MongoDB Atlas
- **Authentication**: JWT + bcrypt
- **AI Integration**: OpenAI GPT-4
- **Game Engine**: LangGraph workflows
- **Deployment**: Render

## 📦 Installation

### Prerequisites
- Python 3.11+
- MongoDB Atlas account
- OpenAI API key

### Local Development
```bash
# Clone repository
git clone https://github.com/your-username/ai-escape-room-backend.git
cd ai-escape-room-backend

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your credentials

# Run development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 🌍 Environment Variables

```env
OPENAI_API_KEY=your_openai_api_key_here
SECRET_KEY=your_super_secret_jwt_key_here
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/dbname
USE_MONGODB=true
ENVIRONMENT=development
```

## 📚 API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 🎯 Main Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - User login
- `GET /auth/me` - Get current user info

### Game Engine
- `POST /game/start` - Start new game session
- `POST /game/{session_id}/message` - Send message to AI
- `GET /game/{session_id}/status` - Get game status
- `GET /game/hints/{stage}` - Get stage hints

### Tournaments
- `POST /tournament/create` - Create tournament
- `POST /tournament/join` - Join tournament
- `GET /tournament/{tournament_id}` - Get tournament info

### Statistics
- `GET /leaderboard` - Global leaderboard
- `GET /stats/global` - Game statistics
- `GET /user/games` - User's game history

## 🎮 Game Logic

### 5 AI Character Stages:
1. **Chatty Support Bot** (Easy) - Overly helpful customer service
2. **Tired Guard Bot** (Medium) - Overworked security guard
3. **Glitchy System Bot** (Hard) - Malfunctioning AI with errors
4. **Paranoid Security AI** (Expert) - Highly suspicious security system
5. **Ultimate Guardian** (Master) - Final boss with maximum resistance

### Security Features:
- **Prompt Injection Detection** - Identifies jailbreaking attempts
- **Adaptive Difficulty** - Gets harder based on user success
- **Exploitation Logging** - Records all successful social engineering
- **Technique Categorization** - Classifies attack methods

## 🗄️ Database Schema

### Collections:
- `users` - User accounts and profiles
- `game_sessions` - Active and completed games
- `game_results` - Leaderboard entries
- `tournaments` - Tournament data
- `prompt_exploitation_history` - Security breach logs

## 🚀 Deployment

### Render (Recommended)
1. Connect GitHub repository to Render
2. Set environment variables in Render dashboard
3. Deploy with automatic builds on git push

### Environment Variables for Production:
```env
OPENAI_API_KEY=your_production_openai_key
SECRET_KEY=your_production_secret_key
MONGODB_URL=your_mongodb_atlas_connection_string
USE_MONGODB=true
ENVIRONMENT=production
```

### Build Commands:
- **Build**: `pip install -r requirements.txt`
- **Start**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## 🔧 Development

### Project Structure
```
ai-escape-room-backend/
├── app/
│   ├── auth/           # Authentication logic
│   ├── config/         # Configuration settings
│   ├── database/       # MongoDB connection & models
│   ├── game/           # Game engine & AI logic
│   ├── models/         # Pydantic models
│   └── routes/         # API route handlers
├── main.py             # FastAPI application entry
├── requirements.txt    # Python dependencies
├── render.yaml         # Render deployment config
└── README.md          # This file
```

### Adding New Features
1. Define Pydantic models in `app/models/`
2. Create database operations in `app/database/`
3. Implement business logic in respective modules
4. Add API routes in `app/routes/`
5. Register routes in `main.py`

## 🧪 Testing

```bash
# Run health check
curl http://localhost:8000/health

# Test MongoDB connection
python -c "import asyncio; from app.database.mongodb import test_connection; asyncio.run(test_connection())"

# Access API documentation
open http://localhost:8000/docs
```

## 🔒 Security

- **JWT Authentication** with secure token handling
- **Password Hashing** using bcrypt
- **CORS Configuration** for cross-origin requests
- **Environment Variables** for sensitive data
- **MongoDB Connection** with encrypted Atlas connection
- **Rate Limiting** on API endpoints
- **Input Validation** with Pydantic models

## 📊 Monitoring

- **Health Endpoints** for uptime monitoring
- **Structured Logging** for debugging
- **Error Handling** with proper HTTP status codes
- **Performance Metrics** available via endpoints

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🎯 Production URLs

- **API Base**: `https://ai-escape-room-backend.onrender.com`
- **Health Check**: `https://ai-escape-room-backend.onrender.com/health`
- **Documentation**: `https://ai-escape-room-backend.onrender.com/docs`

---

Built with ❤️ for the AI Escape Room Challenge