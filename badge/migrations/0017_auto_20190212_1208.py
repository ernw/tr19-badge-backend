# Generated by Django 2.1.5 on 2019-02-12 11:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('badge', '0016_auto_20190207_1850'),
    ]

    operations = [
        migrations.AlterField(
            model_name='badge',
            name='_image',
            field=models.BinaryField(blank=True, db_column='image'),
        ),
    ]
