"""Universal PDF extraction with bounded Ollama requests and automatic page splitting.

Replacement for documents/extractor.py. No extra dependencies.
"""
import base64
import json
import time

import fitz
import requests
from django.conf import settings

from .schema import validate_page

# Shorter response than repeated per-cell JSON objects.
OUTPUT_SCHEMA = {
    'type': 'object',
    'properties': {
        'blocks': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'kind': {'type': 'string', 'enum': ['heading', 'paragraph', 'list', 'other']},
                'text': {'type': 'string'},
            },
            'required': ['kind', 'text'],
        }},
        'tables': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'title': {'type': 'string'},
                'rows': {'type': 'array', 'items': {
                    'type': 'array', 'items': {'type': 'string'},
                }},
                'merges': {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'integer'}}},
            },
            'required': ['title', 'rows'],
        }},
    },
    'required': ['blocks', 'tables'],
}

PROMPT = (
    'Transcribe ALL visible text in reading order, in its original language. '
    'Return ONLY JSON matching the schema. Do not explain, summarize or invent anything. '
    'Put text outside tables in blocks (heading/paragraph/list/other). '
    'For each table, rows is a 2D array of strings: one array for each row, '
    'one string per column, including headers and empty cells. '
    'Do not repeat table content in blocks. Preserve digits and spelling. '
    'Provide original title in table.title if visible. '
    'If visually merged cells are clear, add merges arrays [row, col, rowspan, colspan] for those cells; '
    'include empty strings as placeholders in rows for covered positions. '
    'This image may be only a fragment of a PDF page.'
)

# Regions are split only if model output is truncated; this preserves speed on easy pages.
MAX_SPLITS = 4
MIN_REGION_HEIGHT = 80  # PDF points; prevent tiny illegible crops


class TruncatedAnswer(RuntimeError):
    pass


def _ask_ollama(image):
    payload = {
        'model': settings.OLLAMA_MODEL,
        'stream': False,
        'think': False,
        'format': OUTPUT_SCHEMA,
        'options': {
            'temperature': 0.2,
            'repeat_penalty': 1.1,
            'repeat_last_n': 128,
            'num_predict': settings.OLLAMA_MAX_TOKENS,
            'num_ctx': 8192
        },
        'messages': [{
            'role': 'user',
            'content': PROMPT,
            'images': [base64.b64encode(image).decode('ascii')],
        }],
    }
    try:
        response = requests.post(
            f'{settings.OLLAMA_URL.rstrip("/")}/api/chat',
            json=payload,
            timeout=(10, settings.OLLAMA_TIMEOUT),
        )
        # Include Ollama's error body (not just '404 Client Error').
        if not response.ok:
            if response.status_code == 500 and 'token repeat limit reached' in response.text.lower():
                raise TruncatedAnswer('Ollama остановила генерацию из-за повторения токенов')
            raise RuntimeError(f'Ollama HTTP {response.status_code}: {response.text[:400]}')
        answer = response.json()
    except requests.Timeout as exc:
        raise RuntimeError(f'Ollama не ответила за {settings.OLLAMA_TIMEOUT} секунд') from exc
    except requests.RequestException as exc:
        raise RuntimeError(f'Ошибка соединения с Ollama: {exc}') from exc
    except ValueError as exc:
        raise RuntimeError('Сервер Ollama вернул не JSON-ответ API') from exc

    message = answer.get('message') or {}
    content = message.get('content') or ''
    reason = answer.get('done_reason', 'unknown')
    if reason == 'length':
        raise TruncatedAnswer(f'Ограничение генерации, content={len(content)} символов')
    if not content.strip():
        raise RuntimeError(
            f'Ollama вернула пустой ответ; done_reason={reason}; '
            f'thinking={len(message.get("thinking") or "")} символов. '
            f'Проверьте модель {settings.OLLAMA_MODEL}.'
        )
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'Невалидный JSON Ollama; done_reason={reason}; начало={content[:120]!r}') from exc
    if not isinstance(data, dict):
        raise RuntimeError('Ответ Ollama должен быть JSON-объектом')
    return data


def _to_page(data):
    """Convert short row arrays to original cell schema used by storage.py."""
    tables = []
    for table in data.get('tables', []):
        cells = []
        for row_idx, row in enumerate(table.get('rows', [])):
            for col_idx, value in enumerate(row):
                cells.append({
                    'row': row_idx, 'col': col_idx,
                    'value': str(value if value is not None else ''),
                    'rowspan': 1, 'colspan': 1,
                })
        merges = table.get('merges') or []
        by_coord = {(c['row'], c['col']): c for c in cells}
        for item in merges:
            if not isinstance(item, list) or len(item) != 4 or not all(type(n) is int for n in item):
                continue
            r, col, rs, cs = item
            if rs < 1 or cs < 1 or r < 0 or col < 0 or r + rs > 500 or col + cs > 100:
                continue
            anchor = by_coord.get((r, col))
            if anchor is None:
                continue
            anchor['rowspan'], anchor['colspan'] = rs, cs
            for rr in range(r, r + rs):
                for cc in range(col, col + cs):
                    if (rr, cc) != (r, col):
                        by_coord.pop((rr, cc), None)
        tables.append({'title': table.get('title', ''), 'cells': list(by_coord.values())})
    return validate_page({'blocks': data.get('blocks', []), 'tables': tables})


def _split_at_whitespace(page, rect):
    """Choose a nearly blank horizontal line around the middle of a crop."""
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), colorspace=fitz.csGRAY,
                          alpha=False, clip=rect)
    width, height = pix.width, pix.height
    samples = pix.samples
    stride = pix.stride
    low, high = int(height * .35), int(height * .65)
    if high <= low:
        return (rect.y0 + rect.y1) / 2
    # Count dark pixels across sampled horizontal lines; minimum is a likely text gap.
    def ink(y):
        line = samples[y * stride:y * stride + width]
        return sum(p < 210 for p in line[::3])
    best = min(range(low, high), key=lambda y: (ink(y), abs(y - height / 2) * .02))
    return rect.y0 + rect.height * best / height


def _vision_region(page, rect, depth=0, log=None):
    dpi = settings.PDF_VISION_DPI
    png = page.get_pixmap(dpi=dpi, alpha=False, clip=rect).tobytes('png')
    try:
        return _to_page(_ask_ollama(png))
    except TruncatedAnswer as exc:
        if depth >= MAX_SPLITS or rect.height < 2 * MIN_REGION_HEIGHT:
            raise RuntimeError(
                f'Фрагмент страницы слишком сложный даже после разделения: {exc}. '
                'Попробуйте увеличить OLLAMA_MAX_TOKENS или улучшить качество скана.'
            ) from exc
        y = _split_at_whitespace(page, rect)
        # Guard against degenerate cropping.
        y = max(rect.y0 + MIN_REGION_HEIGHT, min(y, rect.y1 - MIN_REGION_HEIGHT))
        if log:
            log(f'  JSON не уместился; разделяю область (глубина {depth + 1})')
        top = _vision_region(page, fitz.Rect(rect.x0, rect.y0, rect.x1, y), depth + 1, log)
        bottom = _vision_region(page, fitz.Rect(rect.x0, y, rect.x1, rect.y1), depth + 1, log)
        # WARNING: a table straddling the split can appear as two tables.
        return {'blocks': top['blocks'] + bottom['blocks'],
                'tables': top['tables'] + bottom['tables']}


def extract_page(page, log=None):
    """OCR whole page, then split only if output hits token limit."""
    return _vision_region(page, page.rect, log=log)


def native_page(page):
    blocks = []
    for item in page.get_text('blocks'):
        if len(item) > 4 and isinstance(item[4], str) and item[4].strip():
            blocks.append({'kind': 'paragraph', 'text': item[4].strip()})
    tables = []
    try:
        found = page.find_tables()
        for t in found.tables:
            cells = []
            for row_idx, row in enumerate(t.extract()):
                for col_idx, val in enumerate(row):
                    cells.append({'row': row_idx, 'col': col_idx,
                                  'value': str(val or ''), 'rowspan': 1, 'colspan': 1})
            if cells:
                tables.append({'title': '', 'cells': cells})
        rects = [fitz.Rect(t.bbox) for t in found.tables]
        if rects:
            blocks = [{'kind': 'paragraph', 'text': b[4].strip()}
                      for b in page.get_text('blocks')
                      if len(b) > 4 and isinstance(b[4], str) and b[4].strip()
                      and not any(fitz.Rect(b[:4]).intersects(rect) for rect in rects)]
    except (AttributeError, ValueError):
        pass
    return validate_page({'blocks': blocks, 'tables': tables})


def iter_pages(path, log=None, skip_pages=None, on_error=None):
    skip_pages = set(skip_pages or [])

    with fitz.open(path) as pdf:
        if pdf.needs_pass:
            raise ValueError('Зашифрованные PDF не поддерживаются')

        if len(pdf) > settings.PDF_MAX_PAGES:
            raise ValueError(
                f'Максимум страниц: {settings.PDF_MAX_PAGES}'
            )

        for index, page in enumerate(pdf):
            number = index + 1

            if number in skip_pages:
                if log:
                    log(f'Страница {number}/{len(pdf)}: пропущена (сохранена)')
                continue

            start = time.monotonic()

            try:
                text = page.get_text('text')

                use_native = (
                    not settings.PDF_FORCE_VISION
                    and len(text.strip()) >= settings.PDF_NATIVE_MIN_CHARS
                )

                method = 'PyMuPDF' if use_native else 'Ollama'

                if log:
                    log(f'Страница {number}/{len(pdf)}: {method}')

                if use_native:
                    data = native_page(page)
                else:
                    # extract_page expects a PyMuPDF Page, not PNG bytes.
                    # It renders each region itself and can split long pages.
                    data = extract_page(page, log=log)

                yield number, text, data

                if log:
                    elapsed = time.monotonic() - start
                    log(
                        f'Страница {number} завершена '
                        f'за {elapsed:.1f} сек'
                    )

            except Exception as exc:
                if on_error:
                    on_error(number, exc)
                else:
                    raise
