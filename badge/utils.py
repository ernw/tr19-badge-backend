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


from io import BytesIO
from os import listdir
from os.path import abspath, realpath, dirname, join as joinpath
from builtins import open as bltn_open
import logging

from django.conf import settings

from badge.exceptions import AuthenticationError
from badge.models import Badge, AuthCode

logger = logging.getLogger(__name__)


def get_badge(request, raise_exception=True):
    badge_id = request.META.get('HTTP_X_ID', None)
    session_id = request.META.get('HTTP_AUTHORIZATION', None)
    if badge_id is not None:
        signature = request.META.get('HTTP_X_SIGNATURE', None)
        try:
            badge = Badge.objects.get(id=badge_id)
        except Badge.DoesNotExist:
            if raise_exception:
                raise AuthenticationError('Badge does not exist!')
            return None
        if not signature or bytes.fromhex(signature) != badge.calculate_signature(request):
            if raise_exception:
                raise AuthenticationError('Invalid signature!')
            return None
        return badge
    if session_id is not None:
        try:
            session = AuthCode.objects.get(id=session_id, long_lived=True)
        except AuthCode.DoesNotExist:
            if raise_exception:
                raise AuthenticationError('Invalid session!')
            return None
        return session.badge
    if raise_exception:
        raise AuthenticationError('Invalid request!')
    return None


class SafeTar:

    @staticmethod
    def resolved(x):
        return realpath(abspath(x))

    @staticmethod
    def badpath(path, base):
        # joinpath will ignore base if path is absolute
        return not SafeTar.resolved(joinpath(base, path)).startswith(base)

    @staticmethod
    def badlink(info, base):
        # Links are interpreted relative to the directory containing the link
        tip = SafeTar.resolved(joinpath(base, dirname(info.name)))
        return SafeTar.badpath(info.linkname, base=tip)

    @staticmethod
    def hidden(info, base):
        # Links are interpreted relative to the directory containing the link
        for part in info.name.split('/'):
            if part[0] == '.':
                return True
        return False

    @staticmethod
    def safemembers(members, base, include_hidden, name=None):
        for finfo in members:
            if SafeTar.badpath(finfo.name, base):
                continue
            if finfo.issym() and SafeTar.badlink(finfo, base):
                continue
            if finfo.islnk() and SafeTar.badlink(finfo, base):
                continue
            if not include_hidden and SafeTar.hidden(finfo, base):
                continue
            if name and not finfo.name.startswith('{}/'.format(name)):
                continue
            yield finfo

    @staticmethod
    def extractall(tarfile, path, name=None, include_hidden=False):
        path = SafeTar.resolved(joinpath(settings.MEDIA_ROOT, path))
        tarfile.extractall(path=path, members=SafeTar.safemembers(tarfile, path, include_hidden, name))

    @staticmethod
    def add(tarfile, name, arcname, recursive=True):
        if arcname is None:
            arcname = name

        tarinfo = tarfile.gettarinfo(name, arcname)

        if tarinfo is None:
            return

        tarinfo.uid = 0
        tarinfo.gid = 0
        tarinfo.uname = ''
        tarinfo.gname = ''

        # Append the tar header and data to the archive.
        if tarinfo.isreg():
            with bltn_open(name, "rb") as f:
                tarfile.addfile(tarinfo, f)
        elif tarinfo.isdir():
            tarfile.addfile(tarinfo)
            if recursive:
                for f in sorted(listdir(name)):
                    SafeTar.add(tarfile, joinpath(name, f), joinpath(arcname, f), recursive)
        else:
            tarfile.addfile(tarinfo)


class FileStream(object):

    def __init__(self):
        self.buffer = BytesIO()
        self.offset = 0

    def write(self, s):
        self.buffer.write(s)
        self.offset += len(s)

    def tell(self):
        return self.offset

    def close(self):
        self.buffer.close()

    def pop(self):
        s = self.buffer.getvalue()
        self.buffer.close()

        self.buffer = BytesIO()

        return s


