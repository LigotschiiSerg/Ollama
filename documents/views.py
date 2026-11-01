from pathlib import Path
from django.contrib import messages
from django.db.models import Prefetch
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from .downloader import download_pdf
from .forms import UploadForm, CellForm
from .models import Document, Page, Table, Cell
from .physical_tables import materialize
from .logical_tables import root, fragments
from .table_layout import layout


def index(request):
    if request.method == 'POST':
        form=UploadForm(request.POST,request.FILES)
        if form.is_valid():
            try:
                original_url=form.cleaned_data.get('url') or ''
                pdf=form.cleaned_data.get('pdf') or download_pdf(original_url)
                if not pdf.read(5)==b'%PDF-':
                    raise ValueError('Файл не является PDF')
                pdf.seek(0)
                title=Path(pdf.name).name[:255]
                doc=Document.objects.create(title=title,file=pdf,original_url=original_url)
                messages.success(request,'Файл добавлен в очередь. Запустите обработчик.')
                return redirect('document',pk=doc.pk)
            except Exception as exc:
                form.add_error(None,str(exc))
    else:
        form=UploadForm()
    return render(request,'documents/index.html',{'form':form,'documents':Document.objects.all()[:100]})


def document(request,pk):
    doc=get_object_or_404(Document,pk=pk)
    pages=Page.objects.filter(document=doc).prefetch_related('blocks','tables').order_by('number')
    return render(request,'documents/document.html',{'doc':doc,'pages':pages})


def table(request,pk):
    tab = get_object_or_404(Table.objects.select_related('page__document'),pk=pk)
    main = root(tab)
    parts = fragments(main)
    rows = []
    kind = 'matrix'
    headers = 0
    from .logical_tables import header_signature
    for i, part in enumerate(parts):
        cells = list(part.cells.all())
        part_kind, part_headers, values, owners = layout(part, cells)
        if i == 0:
            kind, headers = part_kind, part_headers
        repeated = i > 0 and header_signature(main) and header_signature(part) == header_signature(main)
        for row_no in range(len(values)):
            if repeated and row_no < part_headers:
                continue
            rows.append({'index': row_no, 'page': part.page.number,
                         'header': i == 0 and row_no < headers,
                         'cells': [c for c in cells if c.row == row_no]})
    return render(request,'documents/table.html', {
        'table': main, 'rows': rows, 'detected_type':kind,
        'detected_headers':headers, 'logical_parts':parts, 'logical_root':main
    })


@require_POST
def edit_cell(request,pk):
    cell=get_object_or_404(Cell,pk=pk)
    form=CellForm(request.POST,instance=cell)
    if form.is_valid():
        form.save()
        materialize(root(cell.table))
        messages.success(request,'Ячейка сохранена')
    else:
        messages.error(request,'Не удалось сохранить ячейку')
    return redirect('table',pk=cell.table_id)


def file_view(request,pk):
    doc=get_object_or_404(Document,pk=pk)
    if not doc.file:
        raise Http404()
    return FileResponse(doc.file.open('rb'),content_type='application/pdf',as_attachment=False,filename=doc.title)


@require_POST
def edit_table(request, pk):
    tab = get_object_or_404(Table, pk=pk)
    kind = request.POST.get('table_type', 'auto')
    if kind not in {'auto', 'matrix', 'key_value', 'hierarchical'}:
        raise Http404()
    try:
        headers = int(request.POST.get('header_rows', '0'))
    except ValueError:
        raise Http404()
    if not 0 <= headers <= 20:
        raise Http404()
    tab.title = request.POST.get('title', '').strip()[:500]
    tab.table_type = kind
    tab.header_rows = headers
    tab.save(update_fields=['title', 'table_type', 'header_rows'])
    materialize(root(tab))
    messages.success(request, 'Название и заголовки сохранены')
    return redirect('table', pk=tab.pk)
