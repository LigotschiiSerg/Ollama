import time
from django.core.management.base import BaseCommand
from documents.models import Document
from documents.services import process

class Command(BaseCommand):
    help = 'Process pending PDFs through local Ollama. Use --watch for a worker loop.'
    def add_arguments(self, parser):
        parser.add_argument('--watch',action='store_true')
        parser.add_argument('--document', type=int, help='Process document by ID (including failed)')
        parser.add_argument('--pages', help='Pages to redo, e.g. 14-16 or 3,8,11')
    def handle(self,*args,**options):
        selected = None
        if options['pages']:
            selected = set()
            for part in options['pages'].split(','):
                pieces = part.strip().split('-')
                if len(pieces) == 1:
                    selected.add(int(pieces[0]))
                elif len(pieces) == 2:
                    a, b = map(int, pieces)
                    if a < 1 or b < a or b-a > 100:
                        raise ValueError('Неверный диапазон страниц')
                    selected.update(range(a, b+1))
                else:
                    raise ValueError('Неверный список страниц')
            if not options['document']:
                raise ValueError('--pages требует --document')
        while True:
            doc = (Document.objects.filter(pk=options['document']).first()
                   if options['document'] else
                   Document.objects.filter(status='pending').order_by('created_at').first())
            if doc:
                self.stdout.write(f'Processing #{doc.pk}: {doc.title}')
                process(doc, log=self.stdout.write, only_pages=selected)
                self.stdout.write(f'Finished: {doc.status} {doc.error[:120]}')
                if options['document']:
                    break
            elif not options['watch']:
                break
            else:
                time.sleep(3)
