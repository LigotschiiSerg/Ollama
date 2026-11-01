from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('documents', '0001_initial')]
    operations = [
        migrations.AddField(model_name='table', name='table_type', field=models.CharField(default='auto', max_length=20)),
        migrations.AddField(model_name='table', name='header_rows', field=models.PositiveSmallIntegerField(default=0)),
    ]
