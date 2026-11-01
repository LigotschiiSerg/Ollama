from django.test import SimpleTestCase
from documents.schema import validate_page

class SchemaTests(SimpleTestCase):
    def test_generic_columns(self):
        page=validate_page({'blocks':[{'kind':'heading','text':'Products'}], 'tables':[{'title':'Inventory','cells':[{'row':0,'col':0,'value':'Preț','rowspan':1,'colspan':1}]}]})
        self.assertEqual(page['tables'][0]['cells'][0]['value'],'Preț')
    def test_duplicate_cells_rejected(self):
        data={'blocks':[],'tables':[{'title':'','cells':[{'row':0,'col':0,'value':'x'},{'row':0,'col':0,'value':'y'}]}]}
        with self.assertRaises(ValueError): validate_page(data)
