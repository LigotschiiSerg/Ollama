from django.db import models


class Document(models.Model):
    STATUS = [('pending','В очереди'),('processing','Обрабатывается'),('done','Готов'),('failed','Ошибка')]
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='pdf/')
    original_url = models.URLField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default='pending', db_index=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True,blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Page(models.Model):
    document = models.ForeignKey(Document,on_delete=models.CASCADE,related_name='pages')
    number = models.PositiveIntegerField()
    text = models.TextField(blank=True)  # raw PyMuPDF text layer, helpful for comparison

    class Meta:
        ordering = ['number']
        constraints = [models.UniqueConstraint(fields=['document','number'],name='unique_document_page')]


class Block(models.Model):
    KINDS = [('heading','Заголовок'),('paragraph','Текст'),('list','Список'),('other','Другое')]
    page = models.ForeignKey(Page,on_delete=models.CASCADE,related_name='blocks')
    order = models.PositiveIntegerField()
    kind = models.CharField(max_length=12,choices=KINDS,default='paragraph')
    text = models.TextField()

    class Meta:
        ordering = ['order']


class Table(models.Model):
    page = models.ForeignKey(Page,on_delete=models.CASCADE,related_name='tables')
    order = models.PositiveIntegerField()
    title = models.CharField(max_length=500,blank=True)
    # Entire model response for lossless auditing; don't edit this on cell updates.
    raw = models.JSONField(default=dict,blank=True)
    table_type = models.CharField(max_length=20, default="auto")
    header_rows = models.PositiveSmallIntegerField(default=0)  # 0 = automatic
    continues_from = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="continuations",
        help_text="Предыдущий фрагмент той же таблицы на другой странице"
    )

    class Meta:
        ordering = ['order']


class Cell(models.Model):
    table = models.ForeignKey(Table,on_delete=models.CASCADE,related_name='cells')
    row = models.PositiveIntegerField()
    col = models.PositiveIntegerField()
    value = models.TextField(blank=True)
    rowspan = models.PositiveIntegerField(default=1)
    colspan = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['row','col']
        constraints = [models.UniqueConstraint(fields=['table','row','col'],name='unique_table_cell')]
