"""Link genuine cross-page table fragments; source cells remain untouched.

Conservative structural evidence: repeated/fuzzy headers, or a continuation
without a new header and with compatible data column types. Ambiguous links
remain separate and are reported for manual verification.
"""
import re
import unicodedata
from difflib import SequenceMatcher
from .models import Table
from .table_layout import layout, column_labels


def root(table):
    seen = set()
    while table.continues_from_id:
        if table.pk in seen:
            raise ValueError('Цикл в связях таблиц')
        seen.add(table.pk)
        table = table.continues_from
    return table


def fragments(table):
    main = root(table)
    return [t for t in Table.objects.filter(page__document_id=main.page.document_id)
            .select_related('page', 'continues_from').prefetch_related('cells')
            .order_by('page__number', 'order', 'pk') if root(t).pk == main.pk]


def shape(table):
    return layout(table, list(table.cells.all()))


def _normalize(text):
    text = unicodedata.normalize('NFKD', str(text).casefold())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'[^\w]+', ' ', text).strip()


def _similar(a, b):
    a, b = _normalize(a), _normalize(b)
    return SequenceMatcher(None, a, b).ratio() if a and b else 0


def header_signature(table):
    kind, n, rows, owners = shape(table)
    if not rows or kind == 'key_value' or not n:
        return ()
    return tuple(_normalize(v) for v in column_labels(kind, n, rows, owners))


def _width(rows):
    return len(rows[0]) if rows else 0


def _cell_type(value):
    s = _normalize(value)
    if not s: return 'empty'
    if re.fullmatch(r'[\d\s,.+\-/]+', s): return 'number'
    if re.search(r'\d', s) and re.search(r'[a-z]', s): return 'mixed'
    return 'text'


def _data_rows(table):
    kind, n, rows, _ = shape(table)
    return rows[n:] if n and len(rows) > n else rows


def _type_similarity(previous, following):
    a = _data_rows(previous)[-min(4, len(_data_rows(previous))):]
    b = _data_rows(following)[:4]
    if not a or not b: return 0
    width = max(_width(a), _width(b))
    if not width: return 0
    scores = []
    for c in range(width):
        av = [_cell_type(r[c]) for r in a if c < len(r) and str(r[c]).strip()]
        bv = [_cell_type(r[c]) for r in b if c < len(r) and str(r[c]).strip()]
        if av and bv:
            # Ignore columns containing only blank / OCR noise.
            scores.append(max(sum(x == y for x in av for y in bv) / (len(av)*len(bv)), 0))
    return sum(scores)/len(scores) if scores else 0


def _header_overlap(previous, following):
    _, _, a, _ = shape(previous)
    _, _, b, _ = shape(following)
    if not a or not b: return 0
    left = a[:min(3, len(a))]
    right = b[:min(3, len(b))]
    # Compare column-by-column to handle OCR differences and swapped header rows.
    best = 0
    for x in left:
        for y in right:
            matched = [_similar(i, j) for i, j in zip(x, y) if i.strip() and j.strip()]
            if len(matched) >= 2:
                best = max(best, sum(v >= .65 for v in matched) / len(matched))
    return best


def _repeated_title(previous, following):
    return bool(previous.title.strip() and following.title.strip() and
                _similar(previous.title, following.title) > .86)


def _looks_new_header(table):
    _, _, rows, _ = shape(table)
    if len(rows) < 3: return False
    # Header-like top: several labelled cells, and the next row contains
    # non-numeric descriptors, unlike typical detail rows.
    first_two = rows[:2]
    populated = [(c, s) for r in first_two for c, s in enumerate(r) if str(s).strip()]
    labels = sum(_cell_type(v) == 'text' for _, v in populated)
    return len(populated) >= 5 and labels / len(populated) >= .75


def _long_form_continuation(prev, current):
    """Text-heavy matrix continued after a page break without repeating headers."""
    a, b = _data_rows(prev), _data_rows(current)
    if not a or not b or len(a[0]) != len(b[0]) or len(a[0]) < 4:
        return False
    def long_cells(rows):
        values = [str(value).strip() for row in rows for value in row if str(value).strip()]
        return len(values) >= 6 and sum(len(v) >= 30 for v in values) / len(values) >= .55
    return long_cells(a) and long_cells(b)


def can_auto_join(prev, current):
    if prev.page.document_id != current.page.document_id or current.page.number != prev.page.number + 1:
        return False
    if current.continues_from_id:
        return False
    pkind, _, prows, _ = shape(prev)
    ckind, _, crows, _ = shape(current)
    if not prows or not crows or pkind == 'key_value' or ckind == 'key_value':
        return False
    pw, cw = _width(prows), _width(crows)
    if min(pw, cw) < 3 or abs(pw - cw) > 1:
        return False
    if prev.title.strip() and current.title.strip() and _similar(prev.title, current.title) < .35:
        return False
    if _repeated_title(prev, current) and pw == cw:
        return True
    overlap = _header_overlap(prev, current)
    if pw == cw and overlap >= .65:
        return True
    # A weak one-column mismatch is possible when the final empty grid column
    # was missed by OCR. Require no repeated heading and strongly compatible
    # body values; do not guess across unrelated tables with a fresh header.
    if _looks_new_header(current):
        return False
    if pw == cw and _type_similarity(prev, current) >= .65:
        return True
    if abs(pw-cw) == 1 and _type_similarity(prev, current) >= .72:
        return True
    if pw == cw and _long_form_continuation(prev, current):
        return True
    return False


def link_continuation(previous, following, *, allow_one_column_mismatch=False):
    if previous.pk == following.pk or previous.page.document_id != following.page.document_id:
        raise ValueError('Фрагменты должны принадлежать одному документу')
    if following.page.number != previous.page.number + 1:
        raise ValueError('Фрагменты должны находиться на соседних страницах')
    if root(previous).pk == following.pk:
        raise ValueError('Циклическая ссылка')
    _, _, a, _ = shape(previous)
    _, _, b, _ = shape(following)
    diff = abs(_width(a) - _width(b))
    if not a or not b or (diff > 0 and not (allow_one_column_mismatch and diff == 1)):
        raise ValueError('Число конечных столбцов различается; проверьте сетку')
    following.continues_from = previous
    following.save(update_fields=['continues_from'])


def auto_link(document):
    by_page = {}
    for item in Table.objects.filter(page__document=document).select_related('page').prefetch_related('cells').order_by('page__number', 'order'):
        by_page.setdefault(item.page.number, []).append(item)
    linked = []
    for number in sorted(by_page):
        before, now = by_page.get(number-1, []), by_page[number]
        if before and now and can_auto_join(before[-1], now[0]):
            link_continuation(before[-1], now[0], allow_one_column_mismatch=True)
            linked.append((before[-1].pk, now[0].pk))
    return linked
