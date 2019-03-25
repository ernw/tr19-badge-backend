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


import base64
import hashlib
from io import BytesIO

import numpy as np
from PIL import Image

from django.db import models

# Create your models here.


class Badge(models.Model):
    id = models.CharField(max_length=64, unique=True, primary_key=True)
    mac = models.CharField(max_length=12)
    name = models.CharField(max_length=255)
    secret = models.CharField(max_length=64)
    _image = models.BinaryField(db_column='image', blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    changed_at = models.DateTimeField(auto_now=True)

    def set_image(self, data):
        if type(data) is list:
            try:
                text = bytes(data)
            except ValueError:
                raise
        elif type(data) is str:
            text = base64.b64decode(data)
        elif type(data) is bytes or type(data) is bytearray:
            text = data.decode('ascii')
        else:
            text = b''
        self._image = text

    def get_image(self):
        return self._image

    image = property(get_image, set_image)

    def render(self):
        if not self._image:
            return b''
        data_bytes = np.array(bytearray(self._image), dtype=np.uint8)
        image = Image.fromarray(np.invert(np.resize(data_bytes, (128, 296))), '1')
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue())

    def __str__(self):
        return 'Badge ({}, {})'.format(self.id, self.name)

    def calculate_signature(self, request):
        h = hashlib.sha256()
        h.update(bytes.fromhex(self.secret))
        h.update(request.method.encode('ascii'))
        h.update(request.path.encode('ascii'))
        h.update(request.body)
        return h.digest()
