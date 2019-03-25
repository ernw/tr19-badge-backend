# Generated by Django 2.1.5 on 2019-02-06 10:16

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('badge', '0010_auto_20190206_1015'),
    ]

    operations = [
        migrations.AlterField(
            model_name='app',
            name='name',
            field=models.CharField(max_length=20, validators=[django.core.validators.RegexValidator(code='invalid_name', message='App name must be Alphanumeric', regex='^[a-zA-Z0-9]+$')]),
        ),
    ]
