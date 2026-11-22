# Участие в разработке

**Язык:** **Русский** · [English](CONTRIBUTING.en.md) · [Қазақша](CONTRIBUTING.kk.md)

Используйте синтетические HTML-фикстуры из `tests/fixtures`. Не добавляйте в
pull request реальные страницы Krisha.kz, SQLite-базы, выгрузки CSV, токены
или копии разрешений. CI не выполняет сетевых запросов к источнику.

Перед pull request:

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

Если меняете разбор HTML, добавьте синтетический случай в тесты и опишите,
какие поля или статусы изменились. Для изменения API обновите OpenAPI и
`docs/api.md`. Живую проверку проводите только на собственном разрешённом
экземпляре и без публикации исходных объявлений.

При добавлении текста в интерфейс обновляйте `web/dist/i18n.js` для русского,
английского и казахского языков. Сохраняйте заголовки, адреса и описания
исходных объявлений без перевода.
