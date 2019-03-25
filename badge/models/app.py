# The BSD 3-Clause License
#
# Copyright (c) 2019 "Malte Heinzelmann" <malte@hnzlmnn.de>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.


import hashlib
import json
import os
import tarfile

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from badge.utils import SafeTar


def tar_path(app, filename):
    return 'apps/{}/v{}.tar'.format(app.slug, app.version)


class App(models.Model):
    name = models.CharField(max_length=20, validators=[
        RegexValidator(
            regex='^[a-zA-Z0-9]+$',
            message='App name must be Alphanumeric',
            code='invalid_name',
        ),
    ])
    version = models.IntegerField()
    title = models.CharField(max_length=42)
    blob = models.FileField(upload_to=tar_path)

    class Meta:
        unique_together = (("name", "version"),)

    def __str__(self):
        return '{}({}, {})'.format(self.title, self.name, self.version)

    @property
    def slug(self):
        return hashlib.md5(self.name.encode('utf8')).hexdigest()

    def extract_path(self):
        return 'apps/{}/v{}/'.format(self.slug, self.version)

    def save(self, *args, **kwargs):
        if not self.pk:
            if App.objects.filter(name=self.name).count() > 0:
                version = App.objects.filter(name=self.name).order_by('-version')[0].version + 1
            else:
                version = 1
            self.version = version
        return super(App, self).save(*args, **kwargs)


@receiver(post_save, sender=App)
def extract_blob(sender, instance: App, created, **kwargs):
    if created:
        archive = tarfile.open(instance.blob.path)
        SafeTar.extractall(archive, instance.extract_path(), instance.name)
    try:
        with open(os.path.join(settings.MEDIA_ROOT, instance.extract_path(), instance.name, 'info.json'), 'w+') as f:
            json.dump(dict(name=instance.name, version=instance.version, title=instance.title), f)
    except Exception:
        raise
