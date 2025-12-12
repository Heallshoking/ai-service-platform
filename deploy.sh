#!/bin/bash

# 🚀 Скрипт автоматического деплоя на Timeweb

cd "$(dirname "$0")"

echo "📦 Добавляем файлы..."
git add .

echo "💾 Создаём коммит..."
git commit -m "Update from deploy script" || echo "Нет изменений для коммита"

echo "🚀 Отправляем на GitHub..."
git push origin main

echo ""
echo "✅ ГОТОВО! Изменения отправлены!"
echo "⏰ Через 3-5 минут обновится на Timeweb"
echo ""
echo "🌐 Проверьте: https://heallshoking-ai-service-platform-mvp-11-12-2025-2f94.twc1.net"
