from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(name='Document', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('title', models.CharField(max_length=255)),
            ('file', models.FileField(upload_to='pdf/')),
            ('original_url', models.URLField(blank=True)),
            ('status', models.CharField(choices=[('pending','В очереди'),('processing','Обрабатывается'),('done','Готов'),('failed','Ошибка')], default='pending',max_length=12,db_index=True)),
            ('error', models.TextField(blank=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('completed_at', models.DateTimeField(blank=True,null=True)),
        ], options={'ordering':['-created_at']}),
        migrations.CreateModel(name='Page', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('number', models.PositiveIntegerField()),
            ('text', models.TextField(blank=True)),
            ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pages', to='documents.document')),
        ], options={'ordering':['number']}),
        migrations.CreateModel(name='Block', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('order', models.PositiveIntegerField()),
            ('kind', models.CharField(choices=[('heading','Заголовок'),('paragraph','Текст'),('list','Список'),('other','Другое')], default='paragraph',max_length=12)),
            ('text', models.TextField()),
            ('page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='blocks',to='documents.page')),
        ], options={'ordering':['order']}),
        migrations.CreateModel(name='Table', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('order', models.PositiveIntegerField()),
            ('title', models.CharField(blank=True,max_length=500)),
            ('raw', models.JSONField(blank=True,default=dict)),
            ('page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='tables',to='documents.page')),
        ], options={'ordering':['order']}),
        migrations.CreateModel(name='Cell', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('row', models.PositiveIntegerField()),
            ('col', models.PositiveIntegerField()),
            ('value', models.TextField(blank=True)),
            ('rowspan', models.PositiveIntegerField(default=1)),
            ('colspan', models.PositiveIntegerField(default=1)),
            ('table', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='cells',to='documents.table')),
        ], options={'ordering':['row','col']}),
        migrations.AddConstraint(model_name='page',constraint=models.UniqueConstraint(fields=('document','number'),name='unique_document_page')),
        migrations.AddConstraint(model_name='cell',constraint=models.UniqueConstraint(fields=('table','row','col'),name='unique_table_cell')),
    ]
