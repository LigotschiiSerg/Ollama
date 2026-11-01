from unittest.mock import patch
from django.test import TestCase
from django.db import connection
from django.core.management import call_command
from documents.physical_tables import sql_name
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from documents.models import Document, Page, Table, Cell
from documents.services import save_page,process

class WorkflowTests(TestCase):
    def test_home_access_without_login(self):
        self.assertEqual(self.client.get(reverse('index')).status_code,200)
    def test_file_upload_and_edit(self):
        f=SimpleUploadedFile('test.pdf',b'%PDF-1.4\n',content_type='application/pdf')
        self.assertEqual(self.client.post(reverse('index'),{'pdf':f}).status_code,302)
        doc=Document.objects.get()
        self.assertEqual(self.client.get(reverse('document',args=[doc.pk])).status_code,200)
        self.assertEqual(self.client.get(reverse('file_view',args=[doc.pk])).status_code,200)
        self.assertEqual(doc.status,'pending')
        save_page(doc,1,'text',{'blocks':[],'tables':[{'title':'Unknown','cells':[{'row':0,'col':0,'value':'Original','rowspan':1,'colspan':1}]}]})
        cell=Cell.objects.get()
        self.assertEqual(self.client.get(reverse('table',args=[cell.table_id])).status_code,200)
        response=self.client.post(reverse('edit_cell',args=[cell.pk]),{'value':'Edited'})
        self.assertEqual(response.status_code,302)
        cell.refresh_from_db()
        self.assertEqual(cell.value,'Edited')
        self.assertEqual(cell.table.raw['cells'][0]['value'],'Original')
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT * FROM "{sql_name(cell.table)}"')
            self.assertEqual(cursor.fetchone(), (1, 'Edited'))
    @patch('documents.services.iter_pages')
    def test_worker(self,iterator):
        doc=Document.objects.create(title='test',file='pdf/test.pdf')
        iterator.return_value=iter([(1,'plain',{'blocks':[{'kind':'paragraph','text':'Hello'}],'tables':[]})])
        process(doc)
        doc.refresh_from_db()
        self.assertEqual(doc.status,'done')
        self.assertEqual(Page.objects.count(),1)

    def test_real_sqlite_tables_and_existing_export(self):
        doc = Document.objects.create(title='pdf', file='pdf/test.pdf')
        data = {'blocks': [], 'tables': [
            {'title': 'First', 'cells': [
                {'row': 0, 'col': 0, 'value': 'Nume', 'rowspan': 1, 'colspan': 1},
                {'row': 0, 'col': 1, 'value': 'Preț', 'rowspan': 1, 'colspan': 1},
                {'row': 1, 'col': 0, 'value': 'Masă', 'rowspan': 1, 'colspan': 1},
                {'row': 1, 'col': 1, 'value': '45', 'rowspan': 1, 'colspan': 1},
            ]},
            {'title': 'Second', 'cells': [
                {'row': 0, 'col': 0, 'value': 'Test', 'rowspan': 1, 'colspan': 1},
            ]},
        ]}
        save_page(doc, 1, '', data)
        first, second = list(Table.objects.order_by('order'))
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT "Nume", "Preț" FROM "{sql_name(first)}" ORDER BY _row_no')
            self.assertEqual(cursor.fetchall(), [('Masă', '45')])
            cursor.execute(f'SELECT COUNT(*) FROM "{sql_name(second)}"')
            self.assertEqual(cursor.fetchone()[0], 1)
        call_command('export_pdf_tables')
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT COUNT(*) FROM "{sql_name(first)}"')
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_reexport_after_title_edit_and_key_value(self):
        doc = Document.objects.create(title='pdf', file='pdf/test.pdf')
        save_page(doc, 1, '', {'blocks': [], 'tables': [{'title': 'Old', 'cells': [
            {'row': 0, 'col': 0, 'value': 'Nivelul calificării', 'rowspan': 1, 'colspan': 1},
            {'row': 0, 'col': 1, 'value': 'Nivelul 6 ISCED', 'rowspan': 1, 'colspan': 1},
            {'row': 1, 'col': 0, 'value': 'Specialitatea', 'rowspan': 1, 'colspan': 1},
            {'row': 1, 'col': 1, 'value': 'Informatica', 'rowspan': 1, 'colspan': 1},
        ]}]})
        table = Table.objects.get()
        old = sql_name(table)
        table.title = 'New'
        table.save(update_fields=['title'])
        from documents.physical_tables import materialize
        materialize(table)
        with connection.cursor() as cursor:
            cursor.execute('SELECT name FROM sqlite_master WHERE type=%s AND name=%s', ['table', old])
            self.assertIsNone(cursor.fetchone())
            cursor.execute(f'SELECT "field", "value" FROM "{sql_name(table)}" ORDER BY _row_no')
            self.assertEqual(cursor.fetchall(), [('Nivelul calificării', 'Nivelul 6 ISCED'), ('Specialitatea', 'Informatica')])
