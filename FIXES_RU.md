# Исправления в этой версии

Главная причина ошибок `not all arguments converted during string formatting`: в `documents/physical_tables.py` SQL для `connection.cursor()` использовал `?` вместе с параметрами. Для курсора Django нужно `%s` даже на SQLite. Исправлены оба запроса поиска имен таблиц.

Исправлен тест, учитывающий перенос строки заголовков в названия столбцов. Добавлен тест повторного экспорта с переименованием и key-value таблицей.

## Установка без потери данных

1. Остановить Django и `process_pdfs`, скопировать старые `db.sqlite3` и `media/` в безопасное место.
2. Распаковать проект. Перенести старые `db.sqlite3` и `media/` в каталог с `manage.py`.
3. Создать/активировать `.venv`, установить `pip install -r requirements.txt`.
4. Выполнить `python manage.py migrate`, затем `python manage.py check` и `python manage.py test documents`.
5. Восстановить SQL-таблицы без Ollama: `python manage.py export_pdf_tables`.
6. Запустить `python manage.py runserver` и отдельный `python manage.py process_pdfs --watch`.

Если документ остался `failed`, вернуть только его в очередь, не затрагивая уже готовые страницы:

`python manage.py shell -c "from documents.models import Document; Document.objects.filter(pk=3, status='failed').update(status='pending', error='')"`

Проверь ID перед запуском; номера страниц, уже сохранённые в `documents_page`, пропускаются.

**Ограничения проверки**: запуск реальной Ollama на компьютере пользователя и интеграционные Django-тесты в текущей среде недоступны.
