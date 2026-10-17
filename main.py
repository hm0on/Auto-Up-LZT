"""Поднятие тем раз в 36 часов. Запуск: python main.py (macOS/Linux)."""

import asyncio
import fcntl
import html
import json
import math
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from LOLZTEAM.Client import Forum

BASE_DIR = Path(__file__).resolve().parent
INTERVAL = 36 * 60 * 60 + 5
RETRY_BASE = 5 * 60
RETRY_MAX = 60 * 60
REQUEST_GAP = 10
COOLDOWN_MARGIN = 5


def cooldown_from_response(response):
    """Остаток КД из errors, без общего интервала «раз в 36 часов»."""
    try:
        body = response.json()
    except (ValueError, TypeError):
        return None
    if not isinstance(body, dict):
        return None

    def messages(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from messages(item)
        elif isinstance(value, list):
            for item in value:
                yield from messages(item)

    unit = r"(\d+)\s*(день|дня|дней|час(?:а|ов)?|минут(?:а|ы|у)?|секунд(?:а|ы|у)?)"
    delays = []
    for message in messages(body.get("errors") or body.get("error")):
        text = html.unescape(re.sub(r"<[^>]*>", " ", message)).lower()
        match = re.search(
            r"вы\s+должны\s+подождать\s+(.+?)\s*,?\s*чтобы\s+поднять\s+(?:эту\s+)?тему",
            text, re.DOTALL,
        )
        if not match:
            continue
        duration = match.group(1).strip().rstrip(",").strip()
        # Не принимаем частично распознанное время, иначе можно сократить КД.
        if not re.fullmatch(rf"{unit}(?:[\s,]+(?:и\s+)?{unit})*", duration):
            continue
        seconds = 0
        for amount, name in re.findall(unit, duration):
            multiplier = (86400 if name in ("день", "дня", "дней") else
                          3600 if name.startswith("час") else
                          60 if name.startswith("минут") else 1)
            seconds += int(amount) * multiplier
        # Некорректный/неожиданный ответ не должен ломать планировщик.
        if seconds <= 366 * 86400:
            delays.append(seconds)
    return max(delays) if delays else None


def configure_logging():
    logger.remove()
    options = {"backtrace": False, "diagnose": False}
    logger.add(sys.stderr, level="INFO", **options)
    logger.add(
        BASE_DIR / "logs" / "autoup.log", level="INFO", rotation="10 MB",
        retention="14 days", encoding="utf-8", **options,
    )


def load_config():
    load_dotenv(BASE_DIR / ".env")
    token = os.getenv("LZT_TOKEN", "").strip()
    if not token:
        raise ValueError("Укажите LZT_TOKEN в .env")
    try:
        thread_ids = list(dict.fromkeys(
            int(value.strip()) for value in os.getenv("LZT_THREAD_IDS", "").split(",")
        ))
    except ValueError:
        raise ValueError("Укажите LZT_THREAD_IDS в .env: ID тем через запятую") from None
    if not thread_ids or any(value <= 0 for value in thread_ids):
        raise ValueError("ID тем должны быть положительными числами")
    return token, thread_ids


def retry_after(headers, now):
    """Retry-After бывает числом секунд или датой HTTP."""
    value = headers.get("Retry-After")
    if value is None:
        return 0
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        try:
            seconds = parsedate_to_datetime(value).timestamp() - now
        except (ValueError, TypeError, OverflowError):
            return 0
    return max(0, seconds) if math.isfinite(seconds) else 0


def inspect_response(response):
    """HTTP 200 — успешный ответ bump; дополнительно проверяем ошибки JSON."""
    try:
        body = response.json()
    except (ValueError, TypeError):
        return False, "ответ не является JSON"
    if not isinstance(body, dict):
        return False, "неожиданный формат JSON"
    error = body.get("errors") or body.get("error")
    if error:
        return False, json.dumps(error, ensure_ascii=False)
    if body.get("success") is False:
        return False, "API вернул success=false"
    if response.status_code != 200:
        return False, f"HTTP {response.status_code}"
    return True, "API подтвердил поднятие"


class State:
    def __init__(self, path, thread_ids):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA synchronous=FULL")
        with self.db:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id INTEGER PRIMARY KEY,
                    next_attempt REAL NOT NULL DEFAULT 0,
                    failures INTEGER NOT NULL DEFAULT 0,
                    last_success REAL,
                    last_status TEXT
                )
            """)
            self.db.executemany(
                "INSERT OR IGNORE INTO threads(thread_id) VALUES (?)",
                [(thread_id,) for thread_id in thread_ids],
            )

    def get(self, thread_id):
        return self.db.execute(
            "SELECT next_attempt, failures FROM threads WHERE thread_id=?", (thread_id,)
        ).fetchone()

    def save(self, thread_id, next_attempt, failures, status, success=False):
        with self.db:
            self.db.execute(
                """UPDATE threads SET next_attempt=?, failures=?, last_status=?,
                   last_success=CASE WHEN ? THEN ? ELSE last_success END
                   WHERE thread_id=?""",
                (next_attempt, failures, status, success, time.time(), thread_id),
            )

    def close(self):
        self.db.close()


async def bump_thread(forum, state, thread_id, token):
    _, failures = state.get(thread_id)
    # После аварии во время запроса не повторяем его сразу при запуске.
    state.save(thread_id, time.time() + RETRY_BASE, failures, "запрос начат")
    server_delay = 0
    cooldown = None
    try:
        # В SDK есть свои повторы: ограничиваем суммарное время на одну тему.
        response = await asyncio.wait_for(forum.threads.bump(thread_id=thread_id), timeout=120)
        success, detail = inspect_response(response)
        server_delay = retry_after(response.headers, time.time())
        if not success:
            cooldown = cooldown_from_response(response)
        detail = f"HTTP {response.status_code}: {detail}"
    except Exception as exc:
        success = False
        detail = f"{type(exc).__name__}: {exc}"

    detail = detail.replace(token, "<TOKEN>")[:2000]
    now = time.time()
    if success:
        next_attempt = now + INTERVAL
        state.save(thread_id, next_attempt, 0, detail, success=True)
        logger.success("Тема {} поднята. Следующее поднятие: {}", thread_id, format_time(next_attempt))
    elif cooldown is not None:
        delay = max(cooldown + COOLDOWN_MARGIN, server_delay)
        next_attempt = now + delay
        state.save(thread_id, next_attempt, 0, detail)
        logger.info(
            "Тема {}: КД форума {} сек. Повтор через {:.0f} сек., в {}",
            thread_id, cooldown, delay, format_time(next_attempt),
        )
    else:
        failures += 1
        delay = max(min(RETRY_BASE * 2 ** min(failures - 1, 10), RETRY_MAX), server_delay)
        next_attempt = now + delay
        state.save(thread_id, next_attempt, failures, detail)
        logger.warning(
            "Тема {}: {}. Повтор №{} через {:.0f} сек., в {}",
            thread_id, detail, failures, delay, format_time(next_attempt),
        )


def format_time(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).astimezone().isoformat(timespec="seconds")


async def run(token, thread_ids):
    state = State(BASE_DIR / "state.sqlite3", thread_ids)
    forum = None
    try:
        # Один event loop: клиент не пересоздаёт сессию на каждый запрос.
        forum = Forum(token=token, timeout=60)
        forum.settings.logger.disable()
        forum.settings.delay.enable()
        logger.info("Запущено. Тем: {}. Интервал: 36 часов + 5 секунд", len(thread_ids))
        while True:
            for thread_id in thread_ids:
                next_attempt, _ = state.get(thread_id)
                if next_attempt <= time.time():
                    await bump_thread(forum, state, thread_id, token)
                    await asyncio.sleep(REQUEST_GAP)
            nearest = min(state.get(thread_id)[0] for thread_id in thread_ids)
            await asyncio.sleep(max(1, min(nearest - time.time(), 60)))
    finally:
        state.close()
        if forum is not None:
            await forum.settings.async_client.close()


def main():
    configure_logging()
    try:
        token, thread_ids = load_config()
        # ОС освобождает блокировку даже при аварии. Файл удалять не нужно.
        with (BASE_DIR / "autoup.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                logger.error("Другая копия скрипта уже запущена")
                return 1
            asyncio.run(run(token, thread_ids))
    except KeyboardInterrupt:
        logger.info("Остановлено пользователем")
    except Exception as exc:
        detail = str(exc)
        token = os.getenv("LZT_TOKEN", "").strip()
        if token:
            detail = detail.replace(token, "<TOKEN>")
        logger.error("Работа остановлена: {}: {}", type(exc).__name__, detail)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
