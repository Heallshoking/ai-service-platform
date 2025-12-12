"""
AI Service Platform - FastAPI Backend
Оптимизировано для Timeweb App Platform
"""
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import os
import json
import sqlite3
from pathlib import Path

# Базовая директория проекта
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Google интеграция
try:
    from google_sync import init_google_integration, sync_order_to_google
    GOOGLE_SYNC_AVAILABLE = True
except ImportError:
    GOOGLE_SYNC_AVAILABLE = False
    print("⚠️ Google интеграция недоступна (установите: pip install google-api-python-client)")

# Калькулятор цен
try:
    from price_calculator import estimate_from_description, PriceCalculator, PriceFactors, ServiceCategory, Urgency, District
    PRICE_CALCULATOR_AVAILABLE = True
except ImportError:
    PRICE_CALCULATOR_AVAILABLE = False
    print("⚠️ Калькулятор цен недоступен")

# ==================== КОНФИГУРАЦИЯ ====================

# Переменные окружения
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/ai_service.db")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ==================== ИНИЦИАЛИЗАЦИЯ БД ====================

def init_database():
    """Инициализация SQLite базы данных"""
    db_dir = Path(DATABASE_PATH).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Таблица мастеров
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS masters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            specializations TEXT NOT NULL,
            city TEXT NOT NULL,
            preferred_channel TEXT DEFAULT 'telegram',
            rating REAL DEFAULT 5.0,
            is_active BOOLEAN DEFAULT 1,
            terminal_active BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица заказов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            client_phone TEXT NOT NULL,
            category TEXT NOT NULL,
            problem_description TEXT NOT NULL,
            address TEXT NOT NULL,
            estimated_price REAL,
            status TEXT DEFAULT 'pending',
            master_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- 🔥 НОВЫЕ ПОЛЯ ДЛЯ ОТСЛЕЖИВАНИЯ
            master_departed_at TIMESTAMP,
            master_arrived_at TIMESTAMP,
            client_phone_revealed BOOLEAN DEFAULT 0,
            master_location_lat REAL,
            master_location_lon REAL,
            route_screenshot_url TEXT,
            google_calendar_event_id TEXT,
            google_task_id TEXT,
            
            FOREIGN KEY (master_id) REFERENCES masters(id)
        )
    """)
    
    # Таблица транзакций
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            platform_fee REAL,
            master_earnings REAL,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)
    
    conn.commit()
    conn.close()

# ==================== FASTAPI APP ====================

app = FastAPI(
    title="AI Service Platform",
    description="Автоматизированная платформа для связи мастеров и клиентов",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Инициализация БД при старте
@app.on_event("startup")
async def startup_event():
    init_database()
    
    # Инициализация Google интеграции
    if GOOGLE_SYNC_AVAILABLE:
        try:
            init_google_integration()
            print("✅ Google Calendar и Tasks синхронизация активна")
        except Exception as e:
            print(f"⚠️ Google интеграция недоступна: {e}")
    
    print(f"🚀 AI Service Platform запущен (Environment: {ENVIRONMENT})")

# ==================== МОДЕЛИ ДАННЫХ ====================

class MasterRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., pattern=r'^\+\d{10,15}$')
    specializations: List[str] = Field(..., min_items=1)
    city: str = Field(..., min_length=2, max_length=50)
    preferred_channel: str = Field(default="telegram")

class ClientRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., pattern=r'^\+\d{10,15}$')
    category: str
    problem_description: str = Field(..., min_length=10)
    address: str = Field(..., min_length=5)
    photos: Optional[List[str]] = None

class JobStatusUpdate(BaseModel):
    status: str = Field(..., pattern=r'^(pending|accepted|in_progress|completed|cancelled)$')

class PaymentProcess(BaseModel):
    job_id: int
    payment_method: str = Field(..., pattern=r'^(cash|card|sbp)$')
    amount: float = Field(..., gt=0)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_db_connection():
    """Получить подключение к БД"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def calculate_pricing(category: str, description: str) -> float:
    """Расчёт цены на основе категории и описания"""
    
    # 🔥 ИСПОЛЬЗОВАТЬ ПРОДВИНУТЫЙ КАЛЬКУЛЯТОР
    if PRICE_CALCULATOR_AVAILABLE:
        try:
            result = estimate_from_description(description, category)
            print(f"✅ Автоматический расчёт: {result['total_price']}₽")
            print(f"   Детали: {result['breakdown']}")
            return result['total_price']
        except Exception as e:
            print(f"⚠️ Ошибка калькулятора: {e}")
    
    # Базовый расчёт (если калькулятор недоступен)
    base_prices = {
        "electrical": 1500,
        "plumbing": 1800,
        "appliance": 2000,
        "general": 1200
    }
    
    base_price = base_prices.get(category, 1500)
    
    # Увеличение цены за срочность или сложность
    if "срочно" in description.lower() or "urgent" in description.lower():
        base_price *= 1.3
    
    if len(description) > 200:  # Сложная задача
        base_price *= 1.2
    
    return round(base_price, 2)

def find_available_master(category: str, city: str) -> Optional[int]:
    """Найти доступного мастера"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ищем мастера по специализации и городу
    cursor.execute("""
        SELECT id FROM masters 
        WHERE is_active = 1 
        AND terminal_active = 1
        AND city = ?
        AND specializations LIKE ?
        ORDER BY rating DESC
        LIMIT 1
    """, (city, f'%{category}%'))
    
    result = cursor.fetchone()
    conn.close()
    
    return result['id'] if result else None

def calculate_platform_fee(amount: float) -> Dict[str, float]:
    """Расчёт комиссий платформы"""
    payment_gateway_fee = amount * 0.02  # 2% платёжный шлюз
    remaining = amount - payment_gateway_fee
    platform_commission = remaining * 0.25  # 25% комиссия платформы
    master_earnings = remaining - platform_commission
    
    return {
        "total": amount,
        "payment_gateway_fee": round(payment_gateway_fee, 2),
        "platform_commission": round(platform_commission, 2),
        "master_earnings": round(master_earnings, 2)
    }

# ==================== API ENDPOINTS ====================

@app.get("/")
async def root():
    """Главная страница - AI чат для клиентов"""
    return FileResponse(STATIC_DIR / "ai-chat.html")

@app.get("/form")
async def form_page():
    """Простая форма для клиентов"""
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/admin")
async def admin_panel():
    """Админ-панель"""
    return FileResponse(STATIC_DIR / "admin.html")

@app.get("/master")
async def master_dashboard():
    """Личный кабинет мастера"""
    return FileResponse(STATIC_DIR / "master-dashboard.html")

@app.get("/track")
async def track_master():
    """Отслеживание мастера для клиента"""
    return FileResponse(STATIC_DIR / "track.html")

@app.get("/api")
async def api_info():
    """Информация об API"""
    return {
        "service": "AI Service Platform",
        "version": "1.0.0",
        "status": "running",
        "environment": ENVIRONMENT,
        "features": {
            "google_calendar": GOOGLE_SYNC_AVAILABLE,
            "google_tasks": GOOGLE_SYNC_AVAILABLE,
            "advanced_pricing": PRICE_CALCULATOR_AVAILABLE,
            "telegram_mini_app": True
        },
        "docs": "/docs"
    }

@app.post("/api/v1/price-estimate")
async def estimate_price(data: dict):
    """
    Автоматическая оценка стоимости услуги
    
    Body:
        {
            "category": "electrical",
            "description": "Описание проблемы",
            "urgency": "normal",  // normal, urgent, emergency
            "district": "center",
            "outlets": 0,
            "switches": 0,
            "time_of_day": "day"  // morning, day, evening, night
        }
    """
    if not PRICE_CALCULATOR_AVAILABLE:
        # Базовый расчёт
        price = calculate_pricing(
            data.get('category', 'electrical'),
            data.get('description', '')
        )
        return {
            "estimated_price": price,
            "breakdown": {"base_price": price},
            "calculator": "basic"
        }
    
    try:
        # Продвинутый расчёт
        result = estimate_from_description(
            data.get('description', ''),
            data.get('category', 'electrical')
        )
        
        return {
            "estimated_price": result['total_price'],
            "breakdown": result['breakdown'],
            "discount": result['discount'],
            "multipliers": result['multipliers'],
            "calculator": "advanced"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка расчёта: {str(e)}")

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# ==================== МАСТЕРА ====================

@app.post("/api/v1/masters/register")
async def register_master(master: MasterRegister):
    """Регистрация нового мастера"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO masters (full_name, phone, specializations, city, preferred_channel)
            VALUES (?, ?, ?, ?, ?)
        """, (
            master.full_name,
            master.phone,
            json.dumps(master.specializations),
            master.city,
            master.preferred_channel
        ))
        
        conn.commit()
        master_id = cursor.lastrowid
        
        return {
            "success": True,
            "master_id": master_id,
            "message": f"Мастер {master.full_name} успешно зарегистрирован",
            "terminal_url": f"/terminal/{master_id}"
        }
    
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Телефон уже зарегистрирован")
    finally:
        conn.close()

@app.post("/api/v1/masters/{master_id}/activate-terminal")
async def activate_terminal(master_id: int):
    """Активация терминала мастера"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE masters SET terminal_active = 1 WHERE id = ?", (master_id,))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "message": "Терминал активирован",
        "terminal_url": f"/terminal/{master_id}"
    }

@app.get("/api/v1/masters/available/{category}")
async def get_available_masters(category: str, city: Optional[str] = None):
    """Получить список доступных мастеров"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT id, full_name, specializations, city, rating
        FROM masters
        WHERE is_active = 1 AND terminal_active = 1
        AND specializations LIKE ?
    """
    params = [f'%{category}%']
    
    if city:
        query += " AND city = ?"
        params.append(city)
    
    query += " ORDER BY rating DESC"
    
    cursor.execute(query, params)
    masters = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {"count": len(masters), "masters": masters}

@app.get("/api/v1/masters/{telegram_id}")
async def get_master_by_telegram(telegram_id: int):
    """Получить информацию о мастере по Telegram ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, full_name, phone, specializations, city, rating, is_active, terminal_active
        FROM masters
        WHERE phone = ?
    """, (f"+{telegram_id}",))  # Временно используем phone как ID
    
    master = cursor.fetchone()
    conn.close()
    
    if not master:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    master_dict = dict(master)
    master_dict['specializations'] = json.loads(master_dict['specializations'])
    return master_dict

@app.patch("/api/v1/masters/{master_id}/terminal")
async def update_terminal_status(master_id: int, data: dict):
    """Обновить статус терминала мастера"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    terminal_active = data.get('terminal_active', False)
    
    cursor.execute("""
        UPDATE masters SET terminal_active = ? WHERE id = ?
    """, (1 if terminal_active else 0, master_id))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "terminal_active": terminal_active}

@app.get("/api/v1/masters/{master_id}/statistics")
async def get_master_statistics(master_id: int):
    """Получить статистику мастера"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Общая статистика
    cursor.execute("""
        SELECT 
            COUNT(*) as completed_jobs,
            COALESCE(SUM(t.master_earnings), 0) as total_earnings
        FROM jobs j
        LEFT JOIN transactions t ON j.id = t.job_id
        WHERE j.master_id = ? AND j.status = 'completed'
    """, (master_id,))
    
    stats = dict(cursor.fetchone())
    
    # За сегодня
    cursor.execute("""
        SELECT 
            COUNT(*) as today_jobs,
            COALESCE(SUM(t.master_earnings), 0) as today_earnings
        FROM jobs j
        LEFT JOIN transactions t ON j.id = t.job_id
        WHERE j.master_id = ? 
        AND DATE(j.created_at) = DATE('now')
        AND j.status = 'completed'
    """, (master_id,))
    
    today = dict(cursor.fetchone())
    stats.update(today)
    
    # За месяц
    cursor.execute("""
        SELECT 
            COUNT(*) as month_jobs,
            COALESCE(SUM(t.master_earnings), 0) as month_earnings
        FROM jobs j
        LEFT JOIN transactions t ON j.id = t.job_id
        WHERE j.master_id = ? 
        AND strftime('%Y-%m', j.created_at) = strftime('%Y-%m', 'now')
        AND j.status = 'completed'
    """, (master_id,))
    
    month = dict(cursor.fetchone())
    stats.update(month)
    
    # Средний рейтинг
    cursor.execute("SELECT rating FROM masters WHERE id = ?", (master_id,))
    master = cursor.fetchone()
    stats['average_rating'] = master['rating'] if master else 5.0
    
    conn.close()
    
    return stats

@app.get("/api/v1/jobs")
async def get_jobs(status: Optional[str] = None, city: Optional[str] = None):
    """Получить список заказов"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    jobs = [dict(row) for row in cursor.fetchall()]
    
    # Добавляем читабельное название категории
    category_names = {
        "electrical": "⚡ Электрика",
        "plumbing": "🚰 Сантехника",
        "appliance": "🔌 Бытовая техника",
        "general": "🔨 Общие работы"
    }
    
    for job in jobs:
        job['category_name'] = category_names.get(job.get('category'), job.get('category'))
    
    conn.close()
    
    return jobs

@app.get("/api/v1/masters/{master_id}/jobs")
async def get_master_jobs_all(master_id: int):
    """Получить все заказы мастера"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM jobs 
        WHERE master_id = ? 
        ORDER BY created_at DESC
    """, (master_id,))
    
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jobs

@app.post("/api/v1/jobs/{job_id}/assign")
async def assign_job_to_master(job_id: int, data: dict):
    """Назначить заказ мастеру"""
    master_id = data.get('master_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE jobs 
        SET master_id = ?, status = 'accepted'
        WHERE id = ? AND status = 'pending'
    """, (master_id, job_id))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=400, detail="Заказ уже назначен или не найден")
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Заказ принят"}

@app.patch("/api/v1/jobs/{job_id}/status")
async def update_job_status(job_id: int, data: dict):
    """Обновить статус заказа"""
    new_status = data.get('status')
    
    if new_status not in ['pending', 'accepted', 'in_progress', 'completed', 'cancelled']:
        raise HTTPException(status_code=400, detail="Неверный статус")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE jobs SET status = ? WHERE id = ?
    """, (new_status, job_id))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "status": new_status}

# ==================== КЛИЕНТЫ (AI) ====================

@app.post("/api/v1/ai/web-form")
async def process_client_request(request: ClientRequest):
    """Обработка заявки от клиента через веб-форму"""
    
    # Расчёт цены
    estimated_price = calculate_pricing(request.category, request.problem_description)
    
    # Поиск мастера
    master_id = find_available_master(request.category, "Москва")  # Пока по умолчанию Москва
    
    # Создание заказа
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO jobs (client_name, client_phone, category, problem_description, address, estimated_price, master_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        request.name,
        request.phone,
        request.category,
        request.problem_description,
        request.address,
        estimated_price,
        master_id,
        'accepted' if master_id else 'pending'
    ))
    
    conn.commit()
    job_id = cursor.lastrowid
    conn.close()
    
    # 🔥 СИНХРОНИЗАЦИЯ С GOOGLE CALENDAR И TASKS
    google_sync_result = {'calendar_event_id': None, 'task_id': None}
    if GOOGLE_SYNC_AVAILABLE and master_id:
        try:
            order_data = {
                'id': job_id,
                'client_name': request.name,
                'client_phone': request.phone,
                'category_name': {
                    'electrical': '⚡ Электрика',
                    'plumbing': '🚠 Сантехника',
                    'appliance': '🔌 Бытовая техника',
                    'general': '🔨 Общие работы'
                }.get(request.category, request.category),
                'problem_description': request.problem_description,
                'address': request.address,
                'estimated_price': estimated_price,
                'preferred_date': datetime.now().strftime('%Y-%m-%d'),
                'preferred_time': '09:00'
            }
            google_sync_result = sync_order_to_google(order_data)
            if google_sync_result['calendar_event_id']:
                print(f"✅ Заказ #{job_id} синхронизирован с Google Calendar")
            if google_sync_result['task_id']:
                print(f"✅ Заказ #{job_id} добавлен в Google Tasks")
        except Exception as e:
            print(f"⚠️ Ошибка синхронизации с Google: {e}")
    
    response = {
        "success": True,
        "job_id": job_id,
        "estimated_price": estimated_price,
        "message": "Заявка принята и обрабатывается AI"
    }
    
    if master_id:
        response["master_assigned"] = True
        response["master_id"] = master_id
        response["message"] = f"Заявка принята! Мастер #{master_id} назначен."
    else:
        response["master_assigned"] = False
        response["message"] = "Заявка принята. Ищем подходящего мастера..."
    
    return response

# ==================== ТЕРМИНАЛ МАСТЕРА ====================

@app.get("/api/v1/terminal/jobs/{master_id}")
async def get_master_jobs(master_id: int, status: Optional[str] = None):
    """Получить заказы мастера"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM jobs WHERE master_id = ?"
    params = [master_id]
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {"count": len(jobs), "jobs": jobs}

@app.get("/api/v1/terminal/jobs/{master_id}/active")
async def get_active_job(master_id: int):
    """Получить активный заказ мастера"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM jobs 
        WHERE master_id = ? AND status IN ('accepted', 'in_progress')
        ORDER BY created_at DESC LIMIT 1
    """, (master_id,))
    
    job = cursor.fetchone()
    conn.close()
    
    if not job:
        return {"active_job": None}
    
    return {"active_job": dict(job)}

@app.patch("/api/v1/terminal/jobs/{master_id}/status/{job_id}")
async def update_job_status(master_id: int, job_id: int, update: JobStatusUpdate):
    """Обновить статус заказа"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE jobs SET status = ?
        WHERE id = ? AND master_id = ?
    """, (update.status, job_id, master_id))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    conn.commit()
    conn.close()
    
    return {"success": True, "status": update.status}

@app.post("/api/v1/terminal/payment/process")
async def process_payment(payment: PaymentProcess):
    """Обработка платежа"""
    
    # Расчёт комиссий
    fees = calculate_platform_fee(payment.amount)
    
    # Сохранение транзакции
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO transactions (job_id, amount, payment_method, platform_fee, master_earnings)
        VALUES (?, ?, ?, ?, ?)
    """, (
        payment.job_id,
        payment.amount,
        payment.payment_method,
        fees['platform_commission'],
        fees['master_earnings']
    ))
    
    # Обновление статуса заказа
    cursor.execute("UPDATE jobs SET status = 'completed' WHERE id = ?", (payment.job_id,))
    
    conn.commit()
    transaction_id = cursor.lastrowid
    conn.close()
    
    return {
        "success": True,
        "transaction_id": transaction_id,
        "breakdown": fees,
        "message": f"Оплата {payment.amount}₽ принята. Мастер получит {fees['master_earnings']}₽"
    }

@app.get("/api/v1/terminal/earnings/{master_id}")
async def get_master_earnings(master_id: int):
    """Получить заработок мастера"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_jobs,
            COALESCE(SUM(t.master_earnings), 0) as total_earnings,
            COALESCE(SUM(t.amount), 0) as total_revenue
        FROM jobs j
        LEFT JOIN transactions t ON j.id = t.job_id
        WHERE j.master_id = ? AND j.status = 'completed'
    """, (master_id,))
    
    result = dict(cursor.fetchone())
    conn.close()
    
    return {
        "master_id": master_id,
        "total_jobs": result['total_jobs'],
        "total_earnings": round(result['total_earnings'], 2),
        "total_revenue": round(result['total_revenue'], 2)
    }

# ==================== СТАТИСТИКА ====================

@app.post("/api/v1/master/depart/{job_id}")
async def master_depart(job_id: int, data: dict):
    """
    🚗 Мастер выехал к клиенту
    Сохранить время выезда и маршрут для клиента
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    location = data.get('location', {})
    route_url = data.get('route_screenshot_url', '')
    
    cursor.execute("""
        UPDATE jobs 
        SET master_departed_at = CURRENT_TIMESTAMP,
            master_location_lat = ?,
            master_location_lon = ?,
            route_screenshot_url = ?,
            status = 'on-the-way'
        WHERE id = ?
    """, (
        location.get('lat'),
        location.get('lon'),
        route_url,
        job_id
    ))
    
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "message": "Выезд зафиксирован. Клиент получил уведомление с маршрутом.",
        "route_url": route_url
    }

@app.post("/api/v1/master/arrive/{job_id}")
async def master_arrive(job_id: int):
    """
    ✅ Мастер нажал "Я НА МЕСТЕ"
    Открыть контакт клиента + обновить Google Calendar
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получить данные заказа
    cursor.execute("""
        SELECT id, client_name, client_phone, google_calendar_event_id
        FROM jobs
        WHERE id = ?
    """, (job_id,))
    
    job = cursor.fetchone()
    if not job:
        conn.close()
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    job_dict = dict(job)
    
    # Обновить статус в БД
    cursor.execute("""
        UPDATE jobs 
        SET master_arrived_at = CURRENT_TIMESTAMP,
            client_phone_revealed = 1,
            status = 'arrived'
        WHERE id = ?
    """, (job_id,))
    
    conn.commit()
    conn.close()
    
    # 🔥 ОТКРЫТЬ КОНТАКТ В GOOGLE CALENDAR
    if GOOGLE_SYNC_AVAILABLE and job_dict.get('google_calendar_event_id'):
        try:
            from google_sync import google_integration
            if google_integration:
                google_integration.reveal_client_contact(
                    job_dict['google_calendar_event_id'],
                    job_dict['client_name'],
                    job_dict['client_phone']
                )
        except Exception as e:
            print(f"⚠️ Ошибка обновления Google Calendar: {e}")
    
    return {
        "success": True,
        "message": "Контакт клиента открыт!",
        "client_phone": job_dict['client_phone'],
        "client_name": job_dict['client_name']
    }

@app.get("/api/v1/client/track/{job_id}")
async def track_master(job_id: int):
    """
    📍 Клиент отслеживает мастера
    Показать маршрут и статус
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            status,
            master_departed_at,
            master_arrived_at,
            master_location_lat,
            master_location_lon,
            route_screenshot_url,
            estimated_price
        FROM jobs
        WHERE id = ?
    """, (job_id,))
    
    job = cursor.fetchone()
    conn.close()
    
    if not job:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    job_dict = dict(job)
    
    return {
        "status": job_dict['status'],
        "departed": bool(job_dict['master_departed_at']),
        "arrived": bool(job_dict['master_arrived_at']),
        "location": {
            "lat": job_dict['master_location_lat'],
            "lon": job_dict['master_location_lon']
        } if job_dict['master_location_lat'] else None,
        "route_url": job_dict['route_screenshot_url'],
        "estimated_price": job_dict['estimated_price']
    }

# ==================== СТАТИСТИКА ====================

@app.get("/api/v1/stats")
async def get_statistics():
    """Общая статистика платформы"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Количество мастеров
    cursor.execute("SELECT COUNT(*) as count FROM masters WHERE is_active = 1")
    masters_count = cursor.fetchone()['count']
    
    # Количество заказов
    cursor.execute("SELECT COUNT(*) as count FROM jobs")
    jobs_count = cursor.fetchone()['count']
    
    # Заказы по статусам
    cursor.execute("SELECT status, COUNT(*) as count FROM jobs GROUP BY status")
    jobs_by_status = {row['status']: row['count'] for row in cursor.fetchall()}
    
    # Общий доход
    cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions")
    total_revenue = cursor.fetchone()['total']
    
    conn.close()
    
    return {
        "masters": {"active": masters_count},
        "jobs": {
            "total": jobs_count,
            "by_status": jobs_by_status
        },
        "revenue": {
            "total": round(total_revenue, 2)
        }
    }

# ==================== ЗАПУСК ====================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
