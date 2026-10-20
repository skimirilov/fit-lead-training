# Fit&Lead — обучение кандидатов

Основная схема: GitHub Pages + Google Apps Script + закрытая Google Таблица. Инструкция в [GOOGLE_SETUP.md](GOOGLE_SETUP.md).

Сервер Apps Script находится в apps-script/Code.gs. Пароли и локальные данные исключены из Git. Реальный URL API настраивается в web/settings.js после авторизации Google и развертывания. Публичная система пока не запущена.

Локальная Python-версия: python3 server.py, http://127.0.0.1:8000/ и /hr/.

Проверка Google-логики: node tests/test_google_backend.mjs. Проверка локального сервера: python3 -m unittest discover -s tests -v.

Порядок блоков: типы блогеров и рекламные форматы → поиск и дубли → аналитика. Названия и описания подготовлены по сценариям заказчика и собраны в web/course-content.js.
