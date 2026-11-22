# Участие в разработке

Используйте синтетические HTML-фикстуры из `tests/fixtures`. Не добавляйте в
pull request реальные страницы Krisha.kz, SQLite-базы, выгрузки CSV, токены
или копии разрешений. CI не выполняет сетевых запросов к источнику.

Перед pull request:

```sh
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m unittest discover -s tests -q
node --check web/dist/app.js
python -m json.tool web/dist/openapi.json
```

Если меняете разбор HTML, добавьте синтетический случай в тесты и опишите,
какие поля или статусы изменились. Для изменения API обновите OpenAPI и
`docs/api.md`. Живую проверку проводите только на собственном разрешённом
экземпляре и без публикации исходных объявлений.
