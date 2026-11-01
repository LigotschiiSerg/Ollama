from django.test import TransactionTestCase
from django.db import connection
from documents.models import Document, Page, Table, Cell
from documents.logical_tables import auto_link, link_continuation, fragments
from documents.physical_tables import export_document, sql_name


class ContinuationTests(TransactionTestCase):
    def make(self, doc, page_no, headers, rows, title='CURRICULUM'):
        p = Page.objects.create(document=doc, number=page_no)
        t = Table.objects.create(page=p, order=0, title=title)
        for r, line in enumerate(([headers] if headers else []) + rows):
            for c, val in enumerate(line):
                Cell.objects.create(table=t, row=r, col=c, value=val)
        return t

    def test_merge_repeated_header_one_export(self):
        d = Document.objects.create(title='plan', file='pdf/test.pdf')
        first = self.make(d, 1, ['Code', 'Title'], [['001', 'Math']])
        second = self.make(d, 2, ['Code', 'Title'], [['002', 'Physics']])
        self.assertEqual(auto_link(d), [(first.pk, second.pk)])
        names = export_document(d)
        self.assertEqual(len(names), 1)
        self.assertEqual(len(fragments(first)), 2)
        with connection.cursor() as cur:
            cur.execute(f'SELECT "_source_page", "Code", "Title" FROM "{sql_name(first)}" ORDER BY _row_no')
            self.assertEqual(cur.fetchall(), [(1, '001', 'Math'), (2, '002', 'Physics')])

    def test_manual_merge_without_repeated_header(self):
        d = Document.objects.create(title='plan', file='pdf/test.pdf')
        first = self.make(d, 1, ['Code','Title'], [['001','Math']], title='')
        second = self.make(d, 2, None, [['002','Physics']], title='')
        self.assertEqual(auto_link(d), [])
        link_continuation(first, second)
        self.assertEqual(len(export_document(d)), 1)
        with connection.cursor() as cur:
            cur.execute(f'SELECT "_source_page", "Code", "Title" FROM "{sql_name(first)}" ORDER BY _row_no')
            self.assertEqual(cur.fetchall(), [(1, '001', 'Math'), (2, '002', 'Physics')])

    def test_unrelated_tables_not_joined(self):
        d = Document.objects.create(title='plan', file='pdf/test.pdf')
        self.make(d, 1, ['Code', 'Title'], [['001', 'Math']], title='AAA')
        self.make(d, 2, ['Year', 'Hours'], [['2026', '50']], title='BBB')
        self.assertEqual(auto_link(d), [])
        self.assertEqual(len(export_document(d)), 2)

    def test_three_pages_without_repeated_heading(self):
        d = Document.objects.create(title='plan', file='pdf/test.pdf')
        first = self.make(d, 1, ['Code', 'Course', 'Hours', 'ECTS'],
                          [['F.01.O.001', 'Mathematics', '150', '5']], title='')
        second = self.make(d, 2, None,
                           [['F.02.O.002', 'Physics', '120', '4'],
                            ['F.02.O.003', 'Programming', '150', '5']], title='')
        third = self.make(d, 3, None, [['F.03.O.004', 'Databases', '120', '4']], title='')
        joins = auto_link(d)
        self.assertEqual(joins, [(first.pk, second.pk), (second.pk, third.pk)])
        names = export_document(d)
        self.assertEqual(len(names), 1)
        with connection.cursor() as cur:
            cur.execute(f'SELECT "_source_page" FROM "{sql_name(first)}" ORDER BY "_row_no"')
            self.assertEqual([r[0] for r in cur.fetchall()], [1, 2, 2, 3])

    def test_one_missing_trailing_column(self):
        d = Document.objects.create(title='plan', file='pdf/test.pdf')
        first = self.make(d, 1, ['Course', 'Code', 'Credits', 'CP1', 'CP2'],
                          [['Math', 'F.001', '5', '+', '+']], title='')
        second = self.make(d, 2, None, [['Programming', 'F.002', '5', '+']], title='')
        joins = auto_link(d)
        self.assertEqual(joins, [(first.pk, second.pk)])
        export_document(d)
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{sql_name(first)}"')
            self.assertEqual(cur.fetchone()[0], 2)

    def test_text_heavy_continuation(self):
        d = Document.objects.create(title='plan', file='pdf/test.pdf')
        first = self.make(d, 1, None, [
            ['Knowledge of technical subjects and educational sciences',
             'Description of professional competencies and methodology',
             'Detailed evaluation of educational materials and outcomes',
             'Use of research methods for analysis of learning activities'],
            ['Applying educational research to professional circumstances',
             'Using appropriate training methods and didactic instruments',
             'Methods of analyzing educational activities in practice',
             'Organization of educational and training projects'],
        ], title='')
        second = self.make(d, 2, None, [
            ['Professional activity and use of appropriate tools in practice',
             'Review and design of education and training activities',
             'Communication of methodological research results',
             'Evaluation of results using digital educational methods'],
            ['Continuing professional development for education personnel',
             'Adapting learned skills to professional requirements',
             'Organizing educational projects and scientific studies',
             'Creating effective teaching and learning resources'],
        ], title='')
        self.assertEqual(auto_link(d), [(first.pk, second.pk)])
