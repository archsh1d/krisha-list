# Жобаға үлес қосу

**Тіл:** [Русский](CONTRIBUTING.md) · [English](CONTRIBUTING.en.md) · **Қазақша**

`tests/fixtures` қалтасындағы жасанды HTML үлгілерін пайдаланыңыз. Pull request ішіне нақты Krisha.kz беттерін, SQLite дерекқорларын, CSV экспорттарын, токендерді немесе рұқсат көшірмелерін қоспаңыз. CI дереккөзге желілік сұрау жібермейді.

Pull request ашар алдында:

```sh
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m unittest discover -s tests -q
node --check web/dist/app.js
node --check web/dist/i18n.js
python -m json.tool web/dist/openapi.json
python scripts/localize_openapi.py --check
python scripts/check_docs.py
```

HTML талдауын өзгертсеңіз, жасанды тест мысалын қосып, өзгерген өрістер мен күйлерді сипаттаңыз. API өзгерсе, OpenAPI сипаттамаларын және `docs/api.md`, `docs/en/api.md`, `docs/kk/api.md` файлдарын жаңартыңыз. Тікелей тексеруді тек өз рұқсатыңыз бар инстанцияда жүргізіңіз және нақты хабарландыруларды жарияламаңыз.

Интерфейс мәтінін қосқанда `web/dist/i18n.js` файлын орыс, ағылшын және қазақ тілдері үшін жаңартыңыз. Жиналған хабарландыру тақырыптары, мекенжайлары мен сипаттамалары бастапқы тілінде қалуы тиіс.
