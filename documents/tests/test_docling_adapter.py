from django.test import SimpleTestCase
from documents.docling_extractor import _table

class AdapterTests(SimpleTestCase):
    def test_merged_header_preserved(self):
        class Cell:
            def __init__(self, r, c, er, ec, text):
                self.start_row_offset_idx=r; self.start_col_offset_idx=c
                self.end_row_offset_idx=er; self.end_col_offset_idx=ec; self.text=text
        class Data:
            table_cells=[Cell(0, 0, 1, 2, 'Activități didactice'), Cell(1,0,2,1,'Sem. I'), Cell(1,1,2,2,'Sem. II')]
        class Item:
            data=Data()
            def caption_text(self, doc): return 'CALENDARUL UNIVERSITAR'
        output = _table(Item(), None)
        self.assertEqual(output['title'], 'CALENDARUL UNIVERSITAR')
        self.assertEqual(output['cells'][0]['colspan'], 2)
