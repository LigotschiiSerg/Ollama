"""Extract a PDF with Docling TableFormer, retaining actual merged cells.
The model is loaded once per worker. No Ollama JSON is needed for detected tables.
"""
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from .table_regions import ruled_regions
from functools import lru_cache
import fitz
from django.conf import settings
from .schema import validate_page


@lru_cache(maxsize=1)
def _converter():
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
    except ImportError as exc:
        raise RuntimeError('Не установлен Docling: pip install -r requirements.txt') from exc
    opts = PdfPipelineOptions()
    opts.do_ocr = True
    opts.do_table_structure = True
    opts.table_structure_options.do_cell_matching = True
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})


def _page_number(item):
    prov = getattr(item, 'prov', None) or []
    return int(prov[0].page_no) if prov else None


def _clean(value):
    return str(value or '').encode('utf-8', 'replace').decode('utf-8')


def _table(item, document):
    """Docling uses exclusive end offsets; retain spans instead of flattening."""
    cells = []
    occupied = set()
    for c in item.data.table_cells:
        r = int(c.start_row_offset_idx)
        col = int(c.start_col_offset_idx)
        rs = max(1, int(c.end_row_offset_idx) - r)
        cs = max(1, int(c.end_col_offset_idx) - col)
        if (r, col) in occupied:
            continue
        for rr in range(r, r + rs):
            for cc in range(col, col + cs):
                occupied.add((rr, cc))
        cells.append({'row': r, 'col': col, 'rowspan': rs, 'colspan': cs,
                      'value': _clean(getattr(c, 'text', ''))})
    title = ''
    try:
        title = _clean(item.caption_text(document))
    except (AttributeError, TypeError, ValueError):
        pass
    return {'title': title[:500], 'cells': cells}



def _recover_region(page, region):
    """Try isolated ruled-table crop in Docling; avoids analyzing surrounding prose.

    The temporary one-page PDF preserves the scan pixels; no dependence on
    global page number or text. This never overwrites a successful detection.
    """
    with TemporaryDirectory(prefix='table_region_') as folder:
        target = str(Path(folder) / 'region.pdf')
        cropped = fitz.open()
        try:
            new_page = cropped.new_page(width=region.width, height=region.height)
            new_page.show_pdf_page(new_page.rect, page.parent, page.number, clip=region)
            cropped.save(target)
        finally:
            cropped.close()
        result = _converter().convert(target)
        if not result.document:
            return []
        return [_table(item, result.document) for item in result.document.tables]


def _region_covered(region, tables, page_number, height):
    for item in tables:
        if _page_number(item) != page_number:
            continue
        for prov in getattr(item, 'prov', ()):
            box = getattr(prov, 'bbox', None)
            if box is None:
                continue
            try:
                from docling_core.types.doc import CoordOrigin
                if getattr(box, 'coord_origin', None) == CoordOrigin.BOTTOMLEFT:
                    bounds = fitz.Rect(box.l, height-box.t, box.r, height-box.b)
                else:
                    bounds = fitz.Rect(box.l, box.t, box.r, box.b)
                overlap = bounds & region
                if not overlap.is_empty and overlap.get_area() / region.get_area() > .5:
                    return True
            except (TypeError, AttributeError, ValueError):
                pass
    return False


def iter_docling_pages(path, log=None, skip_pages=None, on_error=None):
    """One document conversion, then one validated result per page.
    Fail rather than silently saving incomplete tables when Docling fails.
    """
    skip_pages = set(skip_pages or ())
    if log:
        log('Docling: анализ структуры документа и таблиц (модели могут загружаться при первом запуске)')
    result = _converter().convert(str(path))
    document = result.document
    tables_by_page = defaultdict(list)
    blocks_by_page = defaultdict(list)
    for table in document.tables:
        number = _page_number(table)
        if number is not None:
            tables_by_page[number].append(_table(table, document))
    for item in document.texts:
        number = _page_number(item)
        if number is None:
            continue
        label = str(getattr(item, 'label', '')).lower()
        kind = ('heading' if any(k in label for k in ('heading', 'title', 'section_header'))
                else 'list' if 'list' in label else 'paragraph')
        value = _clean(getattr(item, 'text', ''))
        if value.strip():
            blocks_by_page[number].append({'kind': kind, 'text': value})
    with fitz.open(path) as pdf:
        if pdf.needs_pass:
            raise ValueError('Зашифрованный PDF')
        if len(pdf) > settings.PDF_MAX_PAGES:
            raise ValueError('Превышен лимит страниц')
        for idx, page in enumerate(pdf, 1):
            if idx in skip_pages:
                if log:
                    log(f'Страница {idx}/{len(pdf)}: сохранена, пропущена')
                continue
            try:
                candidates = ruled_regions(page)
                uncovered = ([r for r in candidates if not _region_covered(r, document.tables, idx, page.rect.height)]
                             if not tables_by_page[idx] else [])
                for region in uncovered:
                    if log:
                        log(f'Страница {idx}: найдена неучтённая область таблицы, проверяю отдельно')
                    recovered = _recover_region(page, region)
                    if not recovered:
                        raise ValueError('Видна таблица с линиями, но Docling не восстановил её структуру')
                    tables_by_page[idx].extend(recovered)
                data = validate_page({'blocks': blocks_by_page[idx], 'tables': tables_by_page[idx]})
                if log:
                    log(f'Страница {idx}/{len(pdf)}: Docling; таблиц: {len(data["tables"])}; ячеек: {sum(len(t["cells"]) for t in data["tables"])}')
                yield idx, page.get_text('text'), data
            except Exception as exc:
                if on_error:
                    on_error(idx, exc)
                else:
                    raise
