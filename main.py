import sqlite3
import json
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

app = FastAPI()

# ---------------------------------------------------------
# 1. CORS SOZLAMALARI (Netlify va Frontend uchun ruxsat)
# ---------------------------------------------------------
origins = [
    "https://thriving-speculoos-3b863c.netlify.app",  # Sizning Netlify manzilingiz
    "http://localhost:5500",                          # Lokal test uchun
    "http://127.0.0.1:5500"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Hozircha hamma joydan ruxsat (Deploymentda o'zgartirish mumkin)
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, DELETE, va h.k.
    allow_headers=["*"],
)

# ---------------------------------------------------------
# 2. PYDANTIC MODELLAR (Ma'lumotlar formatini tekshirish)
# ---------------------------------------------------------

# O'yin yaratish uchun keladigan ma'lumot formati
class Question(BaseModel):
    q: str
    a: str

class GameCreate(BaseModel):
    user_id: int
    game_type: str
    questions: List[Question]  # Savollar ro'yxati

# Pro so'rovi uchun model
class ProRequest(BaseModel):
    user_id: int

# ---------------------------------------------------------
# 3. DATABASE YORDAMCHI FUNKSIYASI
# ---------------------------------------------------------
def get_db_connection():
    conn = sqlite3.connect('twa_games.db') # bot.py bilan bir xil baza
    conn.row_factory = sqlite3.Row  # Natijani lug'at (dict) sifatida olish uchun
    return conn

# ---------------------------------------------------------
# 4. API ENDPOINTLAR
# ---------------------------------------------------------

# A. User ma'lumotlarini olish
@app.get("/api/user/{telegram_id}")
async def get_user(telegram_id: int):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    conn.close()
    
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "telegram_id": user["telegram_id"],
        "full_name": user["full_name"],
        "language": user["language"],
        "is_pro": bool(user["is_pro"])
    }

# B. Userning barcha o'yinlarini olish
@app.get("/api/games/{user_id}")
async def get_user_games(user_id: int):
    conn = get_db_connection()
    games = conn.execute("SELECT * FROM games WHERE creator_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    conn.close()
    
    results = []
    for game in games:
        results.append({
            "id": game["id"],
            "game_type": game["game_type"],
            "share_link": game["share_link"],
            "plays": game["plays"],
            # JSON stringni qayta listga aylantiramiz
            "questions": json.loads(game["questions"]) if game["questions"] else []
        })
    return results

# C. Yangi o'yin yaratish
@app.post("/api/games/create")
async def create_game(game: GameCreate):
    # Noyob havola yaratish (share link)
    share_link = f"game_{uuid.uuid4().hex[:8]}"
    
    # Savollarni JSON stringga aylantirish (SQLite array saqlamaydi)
    questions_json = json.dumps([q.dict() for q in game.questions])
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO games (creator_id, game_type, share_link, questions)
            VALUES (?, ?, ?, ?)
        """, (game.user_id, game.game_type, share_link, questions_json))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
        
    return {"status": "success", "share_link": share_link}

# D. O'yinni o'chirish
@app.delete("/api/games/delete/{share_link}")
async def delete_game(share_link: str):
    conn = get_db_connection()
    conn.execute("DELETE FROM games WHERE share_link = ?", (share_link,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

# E. PRO status so'rash
@app.post("/api/pro/request")
async def request_pro(request: ProRequest):
    conn = get_db_connection()
    
    # Avval user allaqachon so'rov yuborganligini tekshiramiz
    existing = conn.execute(
        "SELECT * FROM pro_requests WHERE user_id = ? AND status = 'pending'", 
        (request.user_id,)
    ).fetchone()
    
    if existing:
        conn.close()
        return {"status": "already_pending", "message": "Sizning so'rovingiz ko'rib chiqilmoqda."}
        
    conn.execute("INSERT INTO pro_requests (user_id) VALUES (?)", (request.user_id,))
    conn.commit()
    conn.close()
    
    return {"status": "pending", "message": "Admin tasdiqlashi uchun yuborildi."}