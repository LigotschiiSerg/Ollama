from django.core.management.base import BaseCommand
from documents.models import Table
from documents.logical_tables import root

class Command(BaseCommand):
    help = 'Показать ID таблиц, страницы и логические группы одного документа'
    def add_arguments(self, parser):
        parser.add_argument('--document', type=int, required=True)
    def handle(self, *args, **options):
        for t in Table.objects.filter(page__document_id=options['document']).select_related('page', 'continues_from').order_by('page__number', 'order'):
            self.stdout.write(f'ID={t.pk} страница={t.page.number} группа={root(t).pk} название={t.title[:70]}')
