@echo off
title TG Monitor Bot
cd /d "D:\УКА\Soft\TG_monitor"

:loop
echo [%date% %time%] Запуск бота...
python bot.py
echo [%date% %time%] Бот впав! Перезапуск через 5 секунд...
timeout /t 5 /nobreak
goto loop