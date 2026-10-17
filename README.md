<div align="center">
  
# <img src="https://upload.wikimedia.org/wikipedia/commons/5/50/Green-animated-arrow.gif" height="36" width="36" alt="Стрелка вверх" /> Auto Up Thread LZT <img src="https://upload.wikimedia.org/wikipedia/commons/5/50/Green-animated-arrow.gif" height="36" width="36" alt="Стрелка вверх" />

Простой софт который помогает автоматически поднимать темы на lolz.live сразу же как только проходит КД на поднятие. 
</div>

## Содержание
- ⚙️ Технологии
- 📦 Использование

## ⚙️ Технологии

- <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" height="30" alt="Python" /></a>
- <a href="https://github.com/AS7RIDENIED/LOLZTEAM"><img src="https://img.shields.io/badge/LOLZTEAM-2.2.1-21A366?style=for-the-badge" height="30" alt="LOLZTEAM 2.2.1 — клиент API форума" /></a>
- <a href="https://docs.python.org/3/library/asyncio.html"><img src="https://img.shields.io/badge/asyncio-3776AB?style=for-the-badge&logo=python&logoColor=white" height="30" alt="asyncio — асинхронные запросы и ожидание" /></a>
- <a href="https://www.sqlite.org/"><img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" height="30" alt="SQLite — сохранение расписания" /></a>
- <a href="https://github.com/Delgan/loguru"><img src="https://img.shields.io/badge/Loguru-0.7.3-F2C811?style=for-the-badge" height="30" alt="Loguru 0.7.3 — логирование" /></a>
- <a href="https://github.com/theskumar/python-dotenv"><img src="https://img.shields.io/badge/python--dotenv-1.2.1-ECD53F?style=for-the-badge&logo=dotenv&logoColor=black" height="30" alt="python-dotenv 1.2.1 — загрузка настроек из .env" /></a>
- <a href="https://systemd.io/"><img src="https://img.shields.io/badge/systemd-000000?style=for-the-badge&logo=systemd&logoColor=white" height="30" alt="systemd — фоновый запуск и автоперезапуск" /></a>

## 📦 Использование

### 🛠️ Установка

Понадобятся **Python 3.11–3.13** и **Linux или macOS**. Скачайте проект и откройте терминал в его папке.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 🔑 Настройка

Создайте файл `.env` рядом с `main.py` по образцу `.env.example`:

```dotenv
LZT_TOKEN=ваш_токен
LZT_THREAD_IDS=1234567,2345678,3456789
```

- **LZT_TOKEN** — API-токен форума с правом `post`. Получить его можно в [настройках аккаунта](https://lolz.team/account/api).
- **LZT_THREAD_IDS** — ID ваших тем через запятую. Например, для ссылки `https://lolz.live/threads/1234567/` ID — `1234567`.

### 🚀 Запуск

В активированном виртуальном окружении выполните:

```bash
python main.py
```

При первом запуске скрипт сразу попробует поднять указанные темы. Если форум вернёт КД, скрипт извлечёт оставшееся время из ответа и повторит запрос после его окончания с запасом **5 секунд**. После успешного поднятия следующая попытка будет через **36 часов и 5 секунд**.

При сетевых и других ошибках повторы идут через **5, 10, 20, 40, 60 минут**, затем раз в час. Ошибка одной темы не останавливает обработку остальных.

### 📝 Логи и расписание

- Логи выводятся в терминал и сохраняются в `logs/autoup.log` с ротацией по **10 MB** и хранением **14 дней**.
- Расписание каждой темы сохраняется в `state.sqlite3` и восстанавливается после перезапуска. Не удаляйте базу, если хотите сохранить время следующих попыток.
- Для остановки нажмите **Ctrl+C**. Для постоянной работы на Linux-сервере используйте службу **systemd** с автозапуском и перезапуском при сбое.

<sub>Анимация стрелки: <a href="https://commons.wikimedia.org/wiki/File:Green-animated-arrow.gif">Giorgi Balakhadze</a>, <a href="https://creativecommons.org/licenses/by-sa/3.0/">CC BY-SA 3.0</a>.</sub>
