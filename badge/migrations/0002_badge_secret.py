# Generated by Django 2.1.5 on 2019-01-27 10:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('badge', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='badge',
            name='secret',
            field=models.CharField(default='', max_length=64),
            preserve_default=False,
        ),
    ]
