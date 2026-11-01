"""Interpret editable table metadata; never alter canonical PDF cell values."""
import re
import unicodedata


def grid(cells):
    """Expand coordinates, retaining span owners for the visual table."""
    if not cells:
        return [], []
    height = max(c.row + c.rowspan for c in cells)
    width = max(c.col + c.colspan for c in cells)
    if height > 500 or width > 100:
        raise ValueError('Слишком большая таблица')
    values = [['' for _ in range(width)] for _ in range(height)]
    owners = [[None for _ in range(width)] for _ in range(height)]
    for cell in cells:
        for row in range(cell.row, cell.row + cell.rowspan):
            for col in range(cell.col, cell.col + cell.colspan):
                if owners[row][col] is not None:
                    raise ValueError('Пересекающиеся объединённые ячейки')
                owners[row][col] = cell
                values[row][col] = cell.value
    return values, owners


def detect_type(cells, rows):
    if not rows:
        return 'matrix'
    if any(c.rowspan > 1 or c.colspan > 1 for c in cells[:]):
        return 'hierarchical'
    if len(rows[0]) == 2 and len(rows) >= 2:
        # Conservatively classify two-column values as key/value when left labels are distinct.
        left = [r[0].strip() for r in rows if r[0].strip()]
        if len(left) >= 2 and len(left) == len(set(left)):
            return 'key_value'
    return 'matrix'


def layout(table, cells):
    rows, owners = grid(cells)
    kind = table.table_type if table.table_type != 'auto' else detect_type(cells, rows)
    if kind == 'key_value':
        header_count = 0
    elif table.header_rows:
        header_count = min(table.header_rows, len(rows))
    elif kind == 'hierarchical':
        # Multi-level headings often have horizontal spans. Count through the last spanning header,
        # then one leaf-label row, only when that last span is not in the body.
        spans = [c.row for c in cells if c.colspan > 1 and c.row < min(4, len(rows) - 1)]
        header_count = min(max(spans) + 2, len(rows) - 1) if spans else min(1, len(rows))
    else:
        header_count = 1 if len(rows) > 1 else 0
    return kind, header_count, rows, owners


def column_labels(kind, header_count, rows, owners):
    if not rows:
        return ['value']
    if kind == 'key_value':
        return ['field', 'value']
    labels = []
    for col in range(len(rows[0])):
        parts = []
        for row in range(header_count):
            cell = owners[row][col]
            value = cell.value.strip().replace('\n', ' ') if cell else ''
            if value and (not parts or parts[-1] != value):
                parts.append(value)
        labels.append(' | '.join(parts) or f'column_{col + 1}')
    return labels


def safe_suffix(text, max_len=45):
    value = unicodedata.normalize('NFKD', str(text)).casefold()
    value = ''.join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r'[^a-z0-9]+', '_', value).strip('_')[:max_len].strip('_')
    return value or 'untitled'


def distinct_names(labels):
    used = {'_row_no'}
    result = []
    for i, label in enumerate(labels):
        base = str(label).strip()[:180] or f'column_{i + 1}'
        name, counter = base, 2
        while name.casefold() in used:
            name = f'{base[:160]}_{counter}'
            counter += 1
        used.add(name.casefold())
        result.append(name)
    return result
