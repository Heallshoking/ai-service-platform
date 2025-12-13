# MVP Quick Start Guide

## Быстрый старт автономной системы

### 1. Проверка установки модулей

```bash
cd /Users/user/Documents/Projects/Github/balt-set.ru/ai-service-platform

# Проверить что файлы созданы
ls -la conversation_manager.py job_file_generator.py schedule_manager.py notification_service.py

# Запустить сервер локально
python main.py
```

Сервер должен запуститься на http://localhost:8000

### 2. Проверка БД

После запуска проверьте что новые таблицы созданы:

```bash
sqlite3 ./data/ai_service.db

# В sqlite консоли:
.tables
# Должно показать: conversations, work_instructions, notifications
.schema conversations
.exit
```

### 3. Тестирование Conversation Manager

Создайте файл `test_conversation.py`:

```python
import sqlite3
from conversation_manager import ConversationManager, ConversationType, ConversationChannel

# Подключиться к БД
conn = sqlite3.connect("./data/ai_service.db")
cm = ConversationManager(conn)

# Создать разговор с клиентом
conversation = cm.create_conversation(
    ConversationType.CLIENT_REQUEST,
    ConversationChannel.TELEGRAM,
    participant_name="Иван Иванов",
    participant_phone="+79001234567"
)

print(f"✅ Разговор создан: {conversation.id}")

# Добавить сообщения
cm.add_message(conversation.id, "user", "Здравствуйте, у меня не работает розетка в гостиной")
cm.add_message(conversation.id, "assistant", "Здравствуйте! Расскажите подробнее, что именно не работает?")
cm.add_message(conversation.id, "user", "Розетка совсем не дает напряжение, проверял телефоном")
cm.add_message(conversation.id, "assistant", "Понятно. Какой у вас адрес?")
cm.add_message(conversation.id, "user", "Калининград, ул. Ленина 10, кв. 5")

print("✅ Сообщения добавлены")

# Получить транскрипт
conv = cm.get_conversation(conversation.id)
print("\n📝 Транскрипт:")
print(conv.get_transcript())

# Завершить разговор с извлеченными данными
cm.complete_conversation(conversation.id, {
    "name": "Иван Иванов",
    "phone": "+79001234567",
    "problem": "не работает розетка",
    "category": "electrical",
    "address": "Калининград, ул. Ленина 10, кв. 5",
    "urgency": "standard"
})

print("\n✅ Разговор завершен!")

conn.close()
```

Запустите:
```bash
python test_conversation.py
```

### 4. Тестирование Schedule Manager

Создайте `test_schedule.py`:

```python
import sqlite3
from schedule_manager import ScheduleManager
from datetime import datetime, time, timedelta

conn = sqlite3.connect("./data/ai_service.db")
sm = ScheduleManager(conn)

# Предположим у нас есть мастер с ID=1
master_id = 1

# Создать расписание на неделю (Пн-Пт, 8:00-20:00)
sm.create_weekly_schedule(
    master_id=master_id,
    default_start="08:00",
    default_end="20:00",
    working_days=[0, 1, 2, 3, 4]  # Пн-Пт
)

print(f"✅ Расписание создано для мастера {master_id}")

# Проверить доступность
today = datetime.now()
is_available = sm.is_master_available(
    master_id=master_id,
    date=today,
    check_time=time(14, 0)  # 14:00
)

print(f"Мастер доступен сегодня в 14:00: {is_available}")

# Найти доступных мастеров
available = sm.get_available_masters(
    specialization="electrical",
    city="Калининград",
    date=today,
    check_time=time(15, 0)
)

print(f"Доступные мастера-электрики в 15:00: {available}")

# Найти лучшего мастера
best = sm.find_best_available_master(
    specialization="electrical",
    city="Калининград",
    date=today
)

print(f"Лучший доступный мастер: {best}")

conn.close()
```

### 5. Тестирование Job File Generator

Создайте `test_job_file.py`:

```python
import sqlite3
import asyncio
from job_file_generator import JobFileGenerator

async def test_job_file():
    conn = sqlite3.connect("./data/ai_service.db")
    jfg = JobFileGenerator(conn)
    
    # Создать тестовый заказ в БД сначала
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO jobs (
            client_name, client_phone, category, 
            problem_description, address, estimated_price, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        "Иван Иванов",
        "+79001234567",
        "electrical",
        "Не работает розетка в гостиной",
        "Калининград, ул. Ленина 10, кв. 5",
        3000.0,
        "pending"
    ))
    conn.commit()
    job_id = cursor.lastrowid
    
    print(f"✅ Заказ создан: #{job_id}")
    
    # Генерировать файл заказа
    job_file = await jfg.generate_job_file(
        job_id=job_id,
        conversation_transcript="[14:05] Клиент: Не работает розетка\\n[14:06] AI: Какой адрес?\\n[14:07] Клиент: ул. Ленина 10",
        problem_description="Не работает розетка в гостиной",
        category="electrical",
        client_info={
            "name": "Иван Иванов",
            "phone": "+79001234567",
            "address": "Калининград, ул. Ленина 10, кв. 5"
        }
    )
    
    print("\n📄 ФАЙЛ ЗАКАЗА ДЛЯ МАСТЕРА:")
    print("="*60)
    print(job_file.to_text())
    print("="*60)
    
    conn.close()

asyncio.run(test_job_file())
```

### 6. Тестирование Notification Service

Создайте `test_notifications.py`:

```python
import sqlite3
import asyncio
from notification_service import NotificationService, NotificationType

async def test_notifications():
    conn = sqlite3.connect("./data/ai_service.db")
    ns = NotificationService(conn)
    
    # Тест 1: Уведомление клиенту о принятии заявки
    print("📲 Отправка уведомления клиенту...")
    success = await ns.notify_client_request_received(
        client_phone="+79001234567",
        job_id=1
    )
    print(f"Результат: {'✅ Успешно' if success else '❌ Ошибка'}")
    
    # Тест 2: Уведомление мастеру о новом заказе
    print("\n📲 Отправка уведомления мастеру...")
    success = await ns.notify_master_new_job(
        master_id="123456789",  # Telegram ID
        job_id=1,
        category="Электрика",
        address="Калининград, ул. Ленина 10",
        earnings=2205.0,
        scheduled_time="Сегодня 14:00"
    )
    print(f"Результат: {'✅ Успешно' if success else '❌ Ошибка'}")
    
    # Проверить историю уведомлений
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications ORDER BY created_at DESC LIMIT 5")
    notifications = cursor.fetchall()
    
    print(f"\n📊 Последние {len(notifications)} уведомлений:")
    for notif in notifications:
        print(f"  - {notif[3]} → {notif[2]} ({notif[9]})")
    
    conn.close()

asyncio.run(test_notifications())
```

### 7. Полный тест workflow

Создайте `test_full_workflow.py`:

```python
import sqlite3
import asyncio
from datetime import datetime, time
from conversation_manager import ConversationManager, ConversationType, ConversationChannel
from job_file_generator import JobFileGenerator
from schedule_manager import ScheduleManager
from notification_service import NotificationService

async def full_workflow_test():
    """Полный тест: от разговора до файла заказа"""
    
    conn = sqlite3.connect("./data/ai_service.db")
    
    # 1. CONVERSATION - Разговор с клиентом
    print("=" * 60)
    print("ЭТАП 1: РАЗГОВОР С КЛИЕНТОМ")
    print("=" * 60)
    
    cm = ConversationManager(conn)
    conversation = cm.create_conversation(
        ConversationType.CLIENT_REQUEST,
        ConversationChannel.TELEGRAM,
        participant_name="Петр Петров",
        participant_phone="+79007654321"
    )
    
    # Симулируем диалог
    messages = [
        ("user", "Здравствуйте, нужен электрик"),
        ("assistant", "Здравствуйте! Что именно нужно сделать?"),
        ("user", "Не работает выключатель в спальне"),
        ("assistant", "Понятно. Какой адрес?"),
        ("user", "Калининград, пр. Мира 25, кв. 12"),
        ("assistant", "Когда удобно?"),
        ("user", "Сегодня после 15:00")
    ]
    
    for role, content in messages:
        cm.add_message(conversation.id, role, content)
    
    # Завершить разговор с данными
    client_data = {
        "name": "Петр Петров",
        "phone": "+79007654321",
        "problem": "не работает выключатель",
        "category": "electrical",
        "address": "Калининград, пр. Мира 25, кв. 12",
        "urgency": "standard",
        "preferred_time": "после 15:00"
    }
    
    cm.complete_conversation(conversation.id, client_data)
    print(f"✅ Разговор завершен: {conversation.id}")
    
    # 2. SCHEDULE - Найти доступного мастера
    print("\n" + "=" * 60)
    print("ЭТАП 2: ПОИСК ДОСТУПНОГО МАСТЕРА")
    print("=" * 60)
    
    sm = ScheduleManager(conn)
    best_master = sm.find_best_available_master(
        specialization="electrical",
        city="Калининград",
        date=datetime.now()
    )
    
    if best_master:
        print(f"✅ Найден мастер: ID {best_master}")
    else:
        print("❌ Доступных мастеров нет")
        best_master = 1  # Fallback для теста
    
    # 3. JOB - Создать заказ
    print("\n" + "=" * 60)
    print("ЭТАП 3: СОЗДАНИЕ ЗАКАЗА")
    print("=" * 60)
    
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO jobs (
            client_name, client_phone, category,
            problem_description, address, estimated_price,
            master_id, status, conversation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_data["name"],
        client_data["phone"],
        client_data["category"],
        client_data["problem"],
        client_data["address"],
        3000.0,
        best_master,
        "assigned",
        conversation.id
    ))
    conn.commit()
    job_id = cursor.lastrowid
    print(f"✅ Заказ создан: #{job_id}")
    
    # 4. JOB FILE - Сгенерировать инструкции
    print("\n" + "=" * 60)
    print("ЭТАП 4: ГЕНЕРАЦИЯ ФАЙЛА ЗАКАЗА")
    print("=" * 60)
    
    jfg = JobFileGenerator(conn)
    job_file = await jfg.generate_job_file(
        job_id=job_id,
        conversation_transcript=cm.get_conversation(conversation.id).get_transcript(),
        problem_description=client_data["problem"],
        category=client_data["category"],
        client_info=client_data
    )
    
    print("✅ Файл заказа сгенерирован")
    print(job_file.to_text())
    
    # 5. NOTIFICATIONS - Отправить уведомления
    print("\n" + "=" * 60)
    print("ЭТАП 5: ОТПРАВКА УВЕДОМЛЕНИЙ")
    print("=" * 60)
    
    ns = NotificationService(conn)
    
    # Клиенту
    await ns.notify_client_master_assigned(
        client_phone=client_data["phone"],
        job_id=job_id,
        master_name="Иван Мастеров",
        address=client_data["address"],
        scheduled_time="Сегодня 15:00",
        price=3000.0
    )
    print("✅ Уведомление клиенту отправлено")
    
    # Мастеру
    await ns.notify_master_new_job(
        master_id=str(best_master),
        job_id=job_id,
        category="Электрика",
        address=client_data["address"],
        earnings=job_file.master_earnings,
        scheduled_time="Сегодня 15:00"
    )
    print("✅ Уведомление мастеру отправлено")
    
    print("\n" + "=" * 60)
    print("✅ ПОЛНЫЙ ЦИКЛ ЗАВЕРШЕН УСПЕШНО!")
    print("=" * 60)
    
    conn.close()

asyncio.run(full_workflow_test())
```

Запустите полный тест:
```bash
python test_full_workflow.py
```

### 8. Деплой на production

```bash
# Перейти в корень проекта
cd /Users/user/Documents/Projects/Github/balt-set.ru

# Закоммитить изменения
git add ai-service-platform/
git commit -m "MVP Phase 1: Core autonomous functions implemented"

# Запушить в dev ветку
git push origin dev

# Или использовать quick deploy
cd ai-service-platform
./quick-push.sh "MVP Phase 1 complete"
```

Система автоматически задеплоится на https://app.balt-set.ru через 2-3 минуты.

### 9. Проверка на production

```bash
# Проверить health endpoint
curl https://app.balt-set.ru/health

# Проверить API
curl https://app.balt-set.ru/api

# Проверить что статика работает
curl https://app.balt-set.ru/admin.html
```

---

**Готово!** Все core модули Phase 1 реализованы и готовы к использованию! 🚀
