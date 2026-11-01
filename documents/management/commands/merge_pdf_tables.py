"""Link adjoining page table fragments as one logical SQL table."""
from django.core.management.base import BaseCommand, CommandError
from documents.models import Table
from documents.logical_tables import link_continuation, fragments, root
from documents.physical_tables import materialize


class Command(BaseCommand):
    help = 'Соединить два фрагмента одной таблицы: merge_pdf_tables PREVIOUS_ID NEXT_ID'

    def add_arguments(self, parser):
        parser.add_argument('previous_id', type=int)
        parser.add_argument('next_id', type=int)

    def handle(self, *args, **options):
        try:
            first = Table.objects.select_related('page').get(pk=options['previous_id'])
            second = Table.objects.select_related('page').get(pk=options['next_id'])
            old_root = root(second)
            if second.continues_from_id and old_root.pk != root(first).pk:
                raise ValueError('Фрагмент уже объединён с другой таблицей')
            link_continuation(first, second)
            name = materialize(first)
            self.stdout.write(self.style.SUCCESS(f'Одна SQLite-таблица: {name}; страниц: {[t.page.number for t in fragments(first)]}'))
        except (Table.DoesNotExist, ValueError) as exc:
            raise CommandError(str(exc)) from exc
