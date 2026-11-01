"""Atomic page writes, resume support and materialized PDF tables."""
from django.conf import settings
import fitz
from django.db import transaction
from django.utils import timezone
from .models import Page, Block, Table, Cell
from .extractor import iter_pages
from .docling_extractor import iter_docling_pages
from .physical_tables import materialize, remove_page_tables, export_document
from .logical_tables import auto_link


def save_page(document, number, text, parsed):
    with transaction.atomic():
        page, _ = Page.objects.get_or_create(document=document, number=number)
        previous_orders = list(page.tables.values_list('order', flat=True))
        page.text = text
        page.save(update_fields=['text'])
        page.blocks.all().delete()
        page.tables.all().delete()
        remove_page_tables(document.pk, number, previous_orders)
        Block.objects.bulk_create([
            Block(page=page, order=i, **block)
            for i, block in enumerate(parsed['blocks'])
        ])
        for order, item in enumerate(parsed['tables']):
            title = item['title'].strip()
            # Use explicit headings only when the model left table title blank.
            # Never borrow the last heading from a page: it may belong to a
            # section AFTER the table. Keep unknown titles blank for review.
            table = Table.objects.create(page=page, order=order, title=title, raw=item)
            Cell.objects.bulk_create([Cell(table=table, **cell) for cell in item['cells']])
            materialize(table)


def process(document, log=None, only_pages=None):
    completed = set(Page.objects.filter(document=document).values_list('number', flat=True))
    if only_pages is not None:
        only_pages = set(only_pages)
        with fitz.open(document.file.path) as pdf:
            total = len(pdf)
        if not only_pages or min(only_pages) < 1 or max(only_pages) > total:
            raise ValueError(f'Страницы должны быть в пределах 1–{total}')
        completed = set(range(1, total + 1)) - only_pages
    errors = []

    def report(text):
        if log:
            log(text)

    def on_error(number, exc):
        message = f'Страница {number}: {exc}'
        errors.append(message)
        report(f'Ошибка: {message[:300]}')

    document.status = 'processing'
    document.error = ''
    document.completed_at = None
    document.save(update_fields=['status', 'error', 'completed_at'])
    report(f'Уже сохранено страниц: {len(completed)}')

    try:
        for number, text, data in (iter_docling_pages if settings.PDF_ENGINE == "docling" else iter_pages)(
            document.file.path, log=log, skip_pages=completed, on_error=on_error
        ):
            try:
                save_page(document, number, text, data)
                completed.add(number)
            except Exception as exc:
                on_error(number, exc)
        # Reconcile continuations after processing the whole document.
        joins = auto_link(document)
        for previous, following in joins:
            report(f'Объединены фрагменты таблицы #{previous} и #{following}')
        export_document(document)
        if errors:
            document.status = 'failed'
            document.error = '\n'.join(errors)[:1500]
        else:
            if only_pages is not None:
                with fitz.open(document.file.path) as pdf:
                    count = len(pdf)
                stored = set(Page.objects.filter(document=document).values_list('number', flat=True))
                if len(stored) != count:
                    document.status = 'failed'
                    document.error = f'Выбранные страницы обработаны; в базе {len(stored)} из {count} страниц.'
                else:
                    document.status = 'done'
                    document.completed_at = timezone.now()
            else:
                document.status = 'done'
                document.completed_at = timezone.now()
    except Exception as exc:
        document.status = 'failed'
        document.error = str(exc)[:1500]
    document.save(update_fields=['status', 'error', 'completed_at'])
