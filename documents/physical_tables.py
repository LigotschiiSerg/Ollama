"""Mirror canonical cells into human-readable SQLite tables (rebuildable exports)."""
from django.db import connection, transaction
from .models import Cell
from .table_layout import layout, column_labels, distinct_names, safe_suffix


def quoted(value):
    return '"' + str(value).replace('"', '""') + '"'


def legacy_name(table):
    return f'pdf_{table.page.document_id}_page_{table.page.number:02d}_table_{table.order + 1:02d}'


def sql_name(table):
    return f'{legacy_name(table)}_{safe_suffix(table.title)}'


def materialize(table):
    """One physical SQLite table per logical table, including all page fragments."""
    from .logical_tables import fragments, root, header_signature, _similar
    main = root(table)
    parts = fragments(main)
    first_cells = list(main.cells.all().order_by('row', 'col'))
    kind, headers, first_rows, owners = layout(main, first_cells)
    columns = distinct_names(column_labels(kind, headers, first_rows, owners))
    if len(columns) > 100:
        raise ValueError('Слишком много столбцов')
    combined = []
    for part in parts:
        part_kind, nheaders, rows, _ = layout(part, list(part.cells.all().order_by('row', 'col')))
        if rows and abs(len(rows[0]) - len(columns)) > 1:
            raise ValueError(f'Несовместимая ширина таблицы на странице {part.page.number}')
        if part.pk == main.pk:
            skip = 0 if kind == 'key_value' else headers
        else:
            # A continuation does not have to repeat its header. Remove it only
            # when the detected header exactly equals the first fragment header.
            # Repeated printed headings may shift one row between pages.
            # Compare each leading row with the first fragment's heading rows;
            # never remove an unmatched data row.
            skip = 0
            for candidate in rows[:3]:
                match = False
                for original in first_rows[:min(3, len(first_rows))]:
                    pair = [(a, b) for a, b in zip(candidate, original) if str(a).strip() and str(b).strip()]
                    if len(pair) >= 2 and sum(_similar(a, b) >= .65 for a, b in pair) / len(pair) >= .65:
                        match = True
                        break
                if not match:
                    break
                skip += 1
        for row in rows[skip:]:
            # OCR may omit a completely blank trailing column on continuations.
            # Pad without modifying the canonical source cells.
            combined.append((part.page.number, (row + [''] * len(columns))[:len(columns)]))
    name = sql_name(main)
    with transaction.atomic():
        with connection.cursor() as cursor:
            for part in parts:
                pattern = legacy_name(part)
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name=%s OR name LIKE %s)", [pattern, pattern + '_%'])
                for (old_name,) in cursor.fetchall():
                    if old_name == pattern or old_name.startswith(pattern + '_'):
                        cursor.execute(f'DROP TABLE IF EXISTS {quoted(old_name)}')
            metadata = ', "_source_page" INTEGER' if len(parts) > 1 else ''
            definition = ', '.join(f'{quoted(c)} TEXT' for c in columns)
            cursor.execute(f'CREATE TABLE {quoted(name)} ("_row_no" INTEGER PRIMARY KEY{metadata}, {definition})')
            placeholders = ', '.join('%s' for _ in range(len(columns) + 1 + (len(parts) > 1)))
            if combined:
                if len(parts) > 1:
                    data = [(i, page, *row) for i, (page, row) in enumerate(combined, 1)]
                else:
                    data = [(i, *row) for i, (_, row) in enumerate(combined, 1)]
                cursor.executemany(f'INSERT INTO {quoted(name)} VALUES ({placeholders})', data)
    return name


def export_document(document):
    """Rebuild canonical SQLite tables, deleting obsolete fragment exports."""
    from .logical_tables import root
    from .models import Table
    tables = list(Table.objects.filter(page__document=document).select_related('continues_from', 'page'))
    roots = {root(table).pk: root(table) for table in tables}
    return [materialize(table) for table in roots.values()]

def remove_page_tables(document_id, page_number, orders):
    with connection.cursor() as cursor:
        for order in orders:
            prefix = f'pdf_{document_id}_page_{page_number:02d}_table_{order + 1:02d}'
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name=%s OR name LIKE %s)", [prefix, prefix + '_%'])
            for (name,) in cursor.fetchall():
                if name == prefix or name.startswith(prefix + '_'):
                    cursor.execute(f'DROP TABLE IF EXISTS {quoted(name)}')
