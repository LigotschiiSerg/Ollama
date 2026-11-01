"""Compact model-output validation. No domain vocabulary or aliases."""

KINDS = {'heading','paragraph','list','other'}
MAX_TEXT = 30000
MAX_ITEMS = 2000


def validate_page(data):
    if not isinstance(data,dict):
        raise ValueError('Ответ модели должен быть JSON-объектом')
    blocks, tables = data.get('blocks'), data.get('tables')
    if not isinstance(blocks,list) or not isinstance(tables,list):
        raise ValueError('Нужны массивы blocks и tables')
    if len(blocks)>MAX_ITEMS or len(tables)>100:
        raise ValueError('Слишком много элементов на странице')
    clean = {'blocks': [], 'tables': []}
    for block in blocks:
        if not isinstance(block,dict) or not isinstance(block.get('text'),str):
            raise ValueError('Неверный текстовый блок')
        kind = block.get('kind','other')
        clean['blocks'].append({'kind':kind if kind in KINDS else 'other','text':block['text'][:MAX_TEXT]})
    for table in tables:
        if not isinstance(table,dict) or not isinstance(table.get('cells'),list):
            raise ValueError('Неверная таблица')
        cells = table['cells']
        if len(cells)>MAX_ITEMS:
            raise ValueError('Слишком много ячеек')
        seen = set()
        cleaned = []
        for cell in cells:
            if not isinstance(cell,dict) or not isinstance(cell.get('value'),str):
                raise ValueError('Неверная ячейка')
            row, col = cell.get('row'), cell.get('col')
            rowspan, colspan = cell.get('rowspan',1), cell.get('colspan',1)
            if (type(row) is not int or type(col) is not int or type(rowspan) is not int or type(colspan) is not int or
                not 0<=row<500 or not 0<=col<100 or not 1<=rowspan<=500 or not 1<=colspan<=100):
                raise ValueError('Недопустимые индексы ячейки')
            if (row,col) in seen:
                raise ValueError('Повторяющиеся координаты ячеек')
            seen.add((row,col))
            cleaned.append({'row':row,'col':col,'rowspan':rowspan,'colspan':colspan,'value':cell['value'][:MAX_TEXT]})
        title = table.get('title','')
        clean['tables'].append({'title':str(title)[:500], 'cells':cleaned})
    return clean
