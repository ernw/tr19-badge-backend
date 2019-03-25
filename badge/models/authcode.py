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


import uuid
import random
from datetime import timedelta

from django.conf import settings
from django.db import models, IntegrityError
from django.utils import timezone

from badge.exceptions import AuthenticationError
from badge.models import Badge


class AuthCodeManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()

    def create_auth_code(self, badge: Badge, long_lived=False, after_delete=False):
        self.delete_expired()
        if AuthCode.objects.filter(long_lived=False, badge__id=badge.id).count() > settings.AUTHCODE_LIMIT:
            raise AuthenticationError('Badge has reached its limit for auth codes for the moment! Try again later.')
        try:
            auth_code = AuthCode.objects.create(
                id=uuid.uuid4() if long_lived else hex(random.getrandbits(4 * settings.AUTHCODE_LENGTH))[2:],
                badge=badge,
                long_lived=long_lived,
            )
            auth_code.save()
            return auth_code
        except IntegrityError as ie:
            pass
        if after_delete:
            raise AuthenticationError('Could not create a AuthCode!')
        self.delete_expired()
        return self.create_authcode(badge, long_lived, True)

    def authenticate_auth_code(self, token):
        try:
            auth_code = super().get_queryset().get(id=token)
        except self.model.DoesNotExist:
            raise AuthenticationError("Invalid token.", 401)

        if auth_code.expired:
            raise AuthenticationError("Session expired.", 401)

        session = AuthCode.objects.create_auth_code(auth_code.badge, True)
        session.save()
        auth_code.delete()
        return session

    def delete_expired(self):
        now = timezone.now()
        lifetime_short = timedelta(seconds=settings.AUTHCODE_LIFETIME)
        lifetime_long = timedelta(seconds=settings.AUTHCODE_LIFETIME)
        expiring_before_short = now - lifetime_short
        expiring_before_long = now - lifetime_long
        super().get_queryset().filter(last_used__lt=expiring_before_short, long_lived__exact=False).delete()
        super().get_queryset().filter(last_used__lt=expiring_before_long, long_lived__exact=True).delete()


class AuthCode(models.Model):
    id = models.CharField(max_length=36, primary_key=True)  # UUID
    badge = models.ForeignKey(Badge, related_name="authcodes", on_delete=models.CASCADE)
    long_lived = models.BooleanField(default=False)
    last_used = models.DateTimeField(auto_now_add=True)

    objects = AuthCodeManager()

    def __str__(self):
        return self.id.__str__()

    @property
    def expired(self):
        lifetime = settings.SESSION_LIFETIME if self.long_lived else settings.AUTHCODE_LIFETIME
        return (timezone.now() - self.last_used).total_seconds() > lifetime
