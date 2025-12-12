#!/bin/bash

# 🚀 Автоматический PUSH на GitHub с force

cd "$(dirname "$0")"

echo "📦 Проверяю количество непушнутых коммитов..."
COMMITS=$(git log origin/main..HEAD --oneline | wc -l | tr -d ' ')
echo "   Найдено коммитов: $COMMITS"

if [ "$COMMITS" -eq "0" ]; then
    echo "✅ Всё уже запушено!"
    exit 0
fi

echo ""
echo "🚀 Пушу $COMMITS коммитов на GitHub (force)..."
echo ""

# Force push (т.к. история разошлась)
git push -f origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ УСПЕШНО! Файлы обновлены на GitHub!"
    echo "⏰ Через 3-5 минут изменения появятся на Timeweb"
    echo ""
    echo "🌐 Проверьте:"
    echo "   https://heallshoking-ai-service-platform-mvp-11-12-2025-2f94.twc1.net/master"
    echo "   https://t.me/ai_service_master_bot/konigelectric"
else
    echo ""
    echo "❌ ОШИБКА! Push не удался."
    echo ""
    echo "📋 РЕШЕНИЕ:"
    echo "1. Откройте: https://github.com/settings/tokens"
    echo "2. Generate new token (classic)"
    echo "3. Поставьте галочку: repo"
    echo "4. Скопируйте токен"
    echo "5. Запустите:"
    echo "   git push -f https://ВАШ_ТОКЕН@github.com/Heallshoking/ai-service-platform.git main"
fi
