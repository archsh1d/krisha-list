# Зерттеу инстанциясын орналастыру

**Тіл:** [Русский](../deployment.md) · [English](../en/deployment.md) · **Қазақша**

## Docker Compose

1. Compose қолдайтын Docker орнатып, репозиторийді көшіріңіз.
2. `python scripts/init_env.py` іске қосыңыз. Пәрмен кездейсоқ токені бар жеке `.env` жасайды, токенді экранға шығармайды және бар файлды қайта жазбайды.
3. `docker compose up --build -d` іске қосыңыз.
4. `docker compose ps` арқылы тексеріп, `http://127.0.0.1:8765/` мекенжайын ашыңыз.

Compose портты хосттың жергілікті loopback мекенжайына байланыстырады. Құпия токен Git елемейтін `.env` файлынан алынады. Контейнер root құқығынсыз жұмыс істейді және SQLite пен көшірмелер үшін `krisha_data` томын қолданады. Тікелей жинау әдепкіде өшірулі. **Kolesa компаниясының жеке жазбаша рұқсатын алғаннан кейін ғана** `.env` ішіне `KRISHA_ENABLE_LIVE=1` орнатып, `docker compose up -d --force-recreate` орындаңыз.

8765 порты бос болмаса, `.env` файлында `KRISHA_HOST_PORT=8766` орнатып, `http://127.0.0.1:8766/` ашыңыз. `compose.yaml` ішіндегі loopback байланысын өзгертпеңіз: жергілікті интерфейс Docker арқылы тек осы мекенжайдан қолжетімді және оның бөлек аутентификациясы жоқ.

Токенді ашпай жергілікті каталогты тексеру:

```sh
docker compose exec krisha-list python -m krisha_list stats --db /app/data/krisha.sqlite3
```

Спецификация `http://127.0.0.1:8765/api/v1/openapi.json` мекенжайында. Өзге `/api/v1` маршруттарына `Authorization: Bearer <token>` қажет. Токенді URL, браузер JavaScript коды, логтар немесе GitHub issue ішіне қоспаңыз.

### Деректер, резервтік көшірме және жаңарту

`krisha_data` томында `/app/data/krisha.sqlite3` және `/app/data/snapshots/` сақталады. `docker compose down` томды сақтайды; `docker compose down -v` **оны жояды**. Жаңарту алдында SQLite резервтік көшірмесін жасаңыз:

```sh
docker compose exec -T krisha-list python -c "import sqlite3; s=sqlite3.connect('/app/data/krisha.sqlite3'); d=sqlite3.connect('/app/data/backup.sqlite3'); s.backup(d); d.close(); s.close()"
docker compose cp krisha-list:/app/data/backup.sqlite3 ./backup.sqlite3
```

`backup.sqlite3` ішінде нақты деректер бар; оны Git-тен тыс сақтаңыз. HTML/JSON көшірмелері көп орын алуы мүмкін; резервтік көшіруден кейін оларды өз сақтау саясатыңызға сай сақтаңыз немесе жойыңыз. Томды, дерекқор дампын, көшірмелерді немесе `.env` файлын ашық репозиторийге ешқашан қоспаңыз.

Кодты жаңарту үшін `git pull`, содан кейін `docker compose up --build -d` орындаңыз. `docker compose logs --tail=100 krisha-list` журналын және күй бетін тексеріңіз.

## Docker қолданбай

Python 3.11+ қажет. Репозиторий түбірінде Windows PowerShell арқылы:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
.venv\Scripts\python -m pip install --no-deps -e .
.venv\Scripts\python -m krisha_list serve --db data/krisha.sqlite3
```

Linux/macOS жүйесінде `python3 -m venv .venv` және `.venv/bin/python` пайдаланыңыз. Веб-файлдар `web/dist` ішінде болғандықтан серверді репозиторий түбірінен іске қосыңыз. Жергілікті интерфейс `http://127.0.0.1:8765/` мекенжайында. Рұқсат етілген тікелей жинауға `--enable-live` қосыңыз. `/api/v1` үшін бөлек құпия файл жасап, `--api-token-file` беріңіз; [API](api.md) бөлімін қараңыз.

## Желілік қолжетімділік

Берілген Compose конфигурациясы бір жергілікті зерттеушіге арналған, ашық Интернет сервисіне дайын емес. Желілік пайдалану үшін HTTPS шлюзі, қолжетімділікті шектеу, квоталар, жеке токендерді басқару, мониторинг және резервтік көшіру қажет. [SECURITY.md](../../SECURITY.kk.md) қараңыз.
