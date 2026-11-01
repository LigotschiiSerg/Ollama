from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('documents', '0002_table_layout')]
    operations = [migrations.AddField(
        model_name='table', name='continues_from',
        field=models.ForeignKey(to='documents.table', null=True, blank=True,
            on_delete=django.db.models.deletion.SET_NULL, related_name='continuations',
            help_text='Предыдущий фрагмент той же таблицы на другой странице'))]
