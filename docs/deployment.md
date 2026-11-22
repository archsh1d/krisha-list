# Развёртывание исследовательского экземпляра

## Docker Compose

1. Установите Docker с поддержкой Compose и клонируйте репозиторий.
2. Запустите `python scripts/init_env.py`. Команда создаёт приватный `.env` с
   случайным токеном, не печатает его и не перезаписывает существующий файл.
3. Запустите `docker compose up --build -d`.
4. Проверьте `docker compose ps` и откройте `http://127.0.0.1:8765/`.

Compose привязывает порт к loopback-адресу хоста. Секрет загружается из `.env`,
который исключён из Git. Контейнер запускается без root-прав, с томом
`krisha_data` для SQLite и снимков. Живой сбор по умолчанию выключен. Установите
`KRISHA_ENABLE_LIVE=1` в `.env` **только после получения собственного
письменного разрешения Kolesa** и выполните
`docker compose up -d --force-recreate`.
Если порт 8765 уже занят, задайте `KRISHA_HOST_PORT=8766` в `.env` и откройте
`http://127.0.0.1:8766/`. Не меняйте loopback-привязку в `compose.yaml`:
локальный интерфейс разрешён через Docker-перенаправление именно для этого
адреса и не имеет отдельной авторизации.

Проверка локального API (токен остаётся на вашем компьютере):

```sh
docker compose exec krisha-list python -m krisha_list stats --db /app/data/krisha.sqlite3
```

Спецификация доступна на `http://127.0.0.1:8765/api/v1/openapi.json`.
Остальные маршруты `/api/v1` требуют `Authorization: Bearer <токен>`.
Не вставляйте токен в URL, браузерный JavaScript, логи или issue GitHub.

### Данные, резервная копия, обновление

Данные находятся в Docker-томе `krisha_data`: `/app/data/krisha.sqlite3` и
`/app/data/snapshots/`. `docker compose down` сохраняет том;
`docker compose down -v` **удаляет его**. Перед обновлением сделайте резервную
копию SQLite штатным механизмом SQLite, например:

```sh
docker compose exec -T krisha-list python -c "import sqlite3; s=sqlite3.connect('/app/data/krisha.sqlite3'); d=sqlite3.connect('/app/data/backup.sqlite3'); s.backup(d); d.close(); s.close()"
```

Затем скопируйте файл из контейнера в безопасное место:

```sh
docker compose cp krisha-list:/app/data/backup.sqlite3 ./backup.sqlite3
```

`backup.sqlite3` тоже содержит реальные данные и должен храниться вне Git.
Снимки HTML/JSON могут занимать значительный объём; храните или удаляйте их
по своей политике хранения после резервного копирования. Никогда не добавляйте
том, дамп базы, снимки или `.env` в публичный репозиторий.

Обновление кода: `git pull`, затем `docker compose up --build -d`. Проверяйте
журнал `docker compose logs --tail=100 krisha-list` и страницу состояния.

## Без Docker

Требуется Python 3.11+. В корне репозитория на Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
.venv\Scripts\python -m pip install --no-deps -e .
.venv\Scripts\python -m krisha_list serve --db data/krisha.sqlite3
```

На Linux/macOS используйте `python3 -m venv .venv` и
`.venv/bin/python` вместо `.venv\Scripts\python`.

Запуск из корня важен: веб-файлы находятся в `web/dist`. Локальный режим
доступен на `http://127.0.0.1:8765/`. Для разрешённого живого сбора добавьте
`--enable-live`. Для `/api/v1` создайте отдельный секретный файл и передайте
`--api-token-file`; подробности в [API](api.md).

## Сетевой доступ

Этот Compose-файл рассчитан на одного локального исследователя. Он не является
готовой конфигурацией для публичного Интернет-сервиса. Перед сетевой
эксплуатацией нужны HTTPS-шлюз, ограничение доступа, квоты, управление
отдельными токенами, мониторинг и резервное копирование. См. [SECURITY.md](../SECURITY.md).
