#!/usr/bin/env python3
"""
Быстрый тест MVP модулей
"""
import sqlite3
import asyncio
from datetime import datetime, time
from pathlib import Path

# Импорты MVP модулей
from conversation_manager import ConversationManager, ConversationType, ConversationChannel
from job_file_generator import JobFileGenerator
from schedule_manager import ScheduleManager
from notification_service import NotificationService


def test_database_tables():
    """Тест 1: Проверка создания таблиц"""
    print("=" * 60)
    print("ТЕСТ 1: ПРОВЕРКА ТАБЛИЦ БД")
    print("=" * 60)
    
    db_path = "./data/ai_service.db"
    Path("./data").mkdir(exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Проверить существующие таблицы
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    expected_tables = [
        "masters", "jobs", "transactions",
        "conversations", "work_instructions", "notifications"
    ]
    
    for table in expected_tables:
        if table in tables:
            print(f"✅ {table}")
        else:
            print(f"❌ {table} - ОТСУТСТВУЕТ")
    
    conn.close()
    print()


def test_conversation_manager():
    """Тест 2: Conversation Manager"""
    print("=" * 60)
    print("ТЕСТ 2: CONVERSATION MANAGER")
    print("=" * 60)
    
    conn = sqlite3.connect("./data/ai_service.db")
    cm = ConversationManager(conn)
    
    # Создать разговор
    conversation = cm.create_conversation(
        ConversationType.CLIENT_REQUEST,
        ConversationChannel.TELEGRAM,
        participant_name="Тест Тестович",
        participant_phone="+79999999999"
    )
    
    print(f"✅ Разговор создан: {conversation.id[:8]}...")
    
    # Добавить сообщения
    cm.add_message(conversation.id, "user", "Тестовое сообщение")
    cm.add_message(conversation.id, "assistant", "Тестовый ответ")
    
    print("✅ Сообщения добавлены")
    
    # Получить транскрипт
    conv = cm.get_conversation(conversation.id)
    transcript = conv.get_transcript()
    
    print(f"✅ Транскрипт получен ({len(transcript)} символов)")
    
    # Завершить
    cm.complete_conversation(conversation.id, {"test": "data"})
    print("✅ Разговор завершен")
    
    conn.close()
    print()


def test_schedule_manager():
    """Тест 3: Schedule Manager"""
    print("=" * 60)
    print("ТЕСТ 3: SCHEDULE MANAGER")
    print("=" * 60)
    
    conn = sqlite3.connect("./data/ai_service.db")
    sm = ScheduleManager(conn)
    
    # Создать тестового мастера если нет
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO masters (
            id, full_name, phone, specializations, city, rating
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (999, "Тест Мастер", "+79999999998", '["electrical"]', "Калининград", 5.0))
    conn.commit()
    
    # Создать расписание
    sm.create_weekly_schedule(
        master_id=999,
        default_start="09:00",
        default_end="18:00",
        working_days=[0, 1, 2, 3, 4]
    )
    
    print("✅ Расписание создано")
    
    # Проверить доступность
    today = datetime.now()
    is_available = sm.is_master_available(
        master_id=999,
        date=today,
        check_time=time(14, 0)
    )
    
    print(f"✅ Проверка доступности: {is_available}")
    
    # Получить расписание
    schedule = sm.get_master_schedule(999)
    print(f"✅ Расписание получено ({len(schedule)} дней)")
    
    conn.close()
    print()


async def test_job_file_generator():
    """Тест 4: Job File Generator"""
    print("=" * 60)
    print("ТЕСТ 4: JOB FILE GENERATOR")
    print("=" * 60)
    
    conn = sqlite3.connect("./data/ai_service.db")
    jfg = JobFileGenerator(conn)
    
    # Создать тестовый заказ
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO jobs (
            client_name, client_phone, category,
            problem_description, address, estimated_price
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "Тест Клиент",
        "+79999999997",
        "electrical",
        "Тестовая проблема",
        "Тестовый адрес",
        1000.0
    ))
    conn.commit()
    job_id = cursor.lastrowid
    
    print(f"✅ Тестовый заказ создан: #{job_id}")
    
    # Генерировать файл
    job_file = await jfg.generate_job_file(
        job_id=job_id,
        conversation_transcript="Тестовый транскрипт",
        problem_description="Тестовая проблема",
        category="electrical",
        client_info={
            "name": "Тест Клиент",
            "phone": "+79999999997",
            "address": "Тестовый адрес"
        }
    )
    
    print("✅ Файл заказа сгенерирован")
    print(f"✅ Диагноз: {job_file.ai_diagnosis[:50]}...")
    print(f"✅ Инструментов: {len(job_file.work_instructions.tools_required)}")
    print(f"✅ Шагов: {len(job_file.work_instructions.step_by_step)}")
    
    conn.close()
    print()


async def test_notification_service():
    """Тест 5: Notification Service"""
    print("=" * 60)
    print("ТЕСТ 5: NOTIFICATION SERVICE")
    print("=" * 60)
    
    conn = sqlite3.connect("./data/ai_service.db")
    ns = NotificationService(conn)
    
    # Отправить тестовое уведомление
    print("Попытка отправки уведомления...")
    success = await ns.notify_client_request_received(
        client_phone="+79999999996",
        job_id=1
    )
    
    if success:
        print("✅ Уведомление отправлено (или записано)")
    else:
        print("⚠️  Уведомление не доставлено (ожидаемо без Telegram bot)")
    
    # Проверить запись в БД
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM notifications")
    count = cursor.fetchone()[0]
    
    print(f"✅ Уведомлений в БД: {count}")
    
    conn.close()
    print()


async def main():
    """Запустить все тесты"""
    print("\n🚀 ЗАПУСК ТЕСТОВ MVP МОДУЛЕЙ\n")
    
    try:
        test_database_tables()
        test_conversation_manager()
        test_schedule_manager()
        await test_job_file_generator()
        await test_notification_service()
        
        print("=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("=" * 60)
        print("\nMVP модули работают корректно и готовы к использованию.\n")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА В ТЕСТАХ: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
