"""Create physical SQLite tables for PDF results already in the database."""
from django.core.management.base import BaseCommand
from documents.models import Document
from documents.physical_tables import export_document
from documents.logical_tables import auto_link


class Command(BaseCommand):
    help = 'Создать отдельные SQLite-таблицы из уже распознанных PDF без повторного OCR.'

    def handle(self, *args, **kwargs):
        count = 0
        for document in Document.objects.all():
            auto_link(document)
            for name in export_document(document):
                self.stdout.write(f'{name} — готово')
                count += 1
        self.stdout.write(self.style.SUCCESS(f'Готово: {count} логических таблиц.'))
