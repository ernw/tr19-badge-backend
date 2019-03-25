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
import binascii
import logging
import tarfile
import json
import uuid
from os import path
import statistics
import requests

from django.http import HttpResponse
from django.conf import settings
import hashlib

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from badge import utils
from badge.exceptions import ApiResponse, AuthenticationError, RegistrationError, ApiException
from badge.models import AuthCode, Badge, Talk, Setting, Vote, Track, ApiKey, Scope, Day, Message
from badge.models.app import App
from badge.models.post import Post
from badge.utils import FileStream, SafeTar

SCOPE_EXPORT = 'export'
SCOPE_POSTS = 'posts'
SCOPE_VOTES = 'votes'

logger = logging.getLogger(__name__)


def index(request):
    return HttpResponse("", status=404)


@csrf_exempt
@require_http_methods(['POST'])
def register(request):
    badge_id = str(request.JSON.get('id', None))
    mac = str(request.JSON.get('mac', None))
    if badge_id is None or mac is None:
        raise RegistrationError('Invalid request!', 400)
    if Badge.objects.filter(id=badge_id).exists():
        raise RegistrationError('Badge already registered!', 403)
    time = timezone.now()
    h = hashlib.sha256()
    h.update(badge_id.encode('ascii'))
    h.update(mac.encode('ascii'))
    h.update(settings.BADGE_KEY.encode('ascii'))
    h.update(str(time).encode('ascii'))
    h.update(uuid.uuid4().bytes)
    secret = h.digest()
    secret_hex = binascii.hexlify(secret)
    badge = Badge.objects.create(id=badge_id, mac=mac, secret=secret_hex.decode('ascii'), registered_at=time)
    badge.save()
    return ApiResponse(dict(secret=badge.secret))


@csrf_exempt
@require_http_methods(['POST'])
def ota_update(request):
    badge = utils.get_badge(request, False)
    if not badge:
        raise AuthenticationError('Unknown badge!', 404)
    installed = request.JSON.get('versions', {})
    logger.debug(','.join(['{}:{}'.format(key, installed[key]) for key in installed.keys()]))
    available = App.objects.values_list('name', flat=True).distinct()
    to_install = []
    for app_name in available:
        app = App.objects.filter(name=app_name).order_by('-version')[0]
        try:
            version = int(installed.get(app.name, -1))
        except TypeError:
            version = -1
        if version < app.version:
            to_install.append(app)
    logger.debug(','.join(available))
    if len(to_install) == 0:
        return ApiResponse('No updates available', 204)
    try:
        buffer = FileStream()
        result = tarfile.open(mode='w', fileobj=buffer)
        for app in to_install:
            SafeTar.add(result, path.join(settings.MEDIA_ROOT, app.extract_path(), app.name), app.name)
        response = HttpResponse(buffer.pop(), status=200, content_type='application/force-download')
        response['Content-Disposition'] = 'attachment; filename=update.tar'
        return response
    except Exception as e:
        pass
    return HttpResponse('Something went wrong!', status=500)


@csrf_exempt
@require_http_methods(['POST', 'GET'])
def auth(request):
    badge = utils.get_badge(request, False)
    token = request.JSON.get('auth', None)
    if badge is None and auth is None:
        raise AuthenticationError('Invalid request!', 404)
    if badge is not None:
        auth_code = AuthCode.objects.create_auth_code(badge)
        return ApiResponse(dict(token=auth_code.id))
    if token is not None:
        session = AuthCode.objects.authenticate_auth_code(token)
        return ApiResponse(dict(token=session.id))
    raise AuthenticationError('Invalid request!', 400)


@csrf_exempt
@require_http_methods(['POST'])
def name(request):
    new_name = request.JSON.get('name', None)
    if new_name is None:
        raise ApiException('No name sent!', 400)
    badge = utils.get_badge(request)
    badge.name = new_name
    badge.save()
    return ApiResponse(status=204)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def image(request):
    badge = utils.get_badge(request)
    data = request.JSON.get('image', None)
    if data is None:
        return ApiResponse(dict(
            image=list(badge.image),
        ))
    try:
        badge.image = data
    except ValueError:
        raise ApiException('Invalid image sent!', 400)
    badge.save()
    return ApiResponse(status=204)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def clear_image(request):
    badge = utils.get_badge(request)
    badge.image = None
    badge.save()
    return ApiResponse(status=204)


@csrf_exempt
@require_http_methods(['POST'])
def settings_update(request):
    badge = utils.get_badge(request)
    badge_settings = Setting.objects.filter(badge=badge)
    schedule = [
        dict(
            name=day.name,
            tracks=[
                dict(
                    name=track.name,
                    talks=[
                        dict(
                            id=talk.id,
                            title=talk.title,
                            speaker=talk.speaker,
                            time=talk.time,
                        )
                        for talk in Talk.objects.filter(track=track).order_by('time')
                    ]
                )
                for track in Track.objects.filter(day=day)
            ]
        )
        for day in Day.objects.all()
    ]
    settings_dict = {}
    for setting in badge_settings:
        settings_dict[setting.key] = json.loads(setting.value)
    return ApiResponse(dict(
        name=badge.name,
        image=base64.b64encode(badge.image).decode('ascii'),
        schedule=schedule,
        settings=settings_dict,
    ))


@csrf_exempt
@require_http_methods(['POST'])
def settings_set(request):
    badge = utils.get_badge(request)
    for key, value in [(key, request.JSON[key]) for key in request.JSON.keys()]:
        Setting.objects.update_or_create(badge=badge, key=key, defaults=dict(value=json.dumps(value)))
    return ApiResponse(status=204)


@csrf_exempt
@require_http_methods(['POST'])
def settings_get(request):
    key = request.POST.get('key', None)
    if key is None:
        raise ApiException('No key set!', 404)
    badge = utils.get_badge(request)
    try:
        setting = Setting.objects.get(badge=badge, key=key)
    except Setting.DoesNotExist:
        raise ApiException('Invalid key set!', 400)
    return ApiResponse({
        key: setting.value
    })


@csrf_exempt
@require_http_methods(['POST'])
def token_submit(request):
    token = request.JSON.get('token', None)
    if token is None:
        raise ApiException('No token sent!', 400)
    logger.debug(token)
    badge = utils.get_badge(request)
    errors = []
    try:
        result = requests.post('https://con.troopers.de/token/submit', data={
            'identifier': badge.id,
            'token': token,
        })
        logger.debug(result.status_code)
        result.raise_for_status()
        data = result.json()
        logger.debug(json.dumps(data))
        errors.extend(data.get('errors', []))
    except Exception as e:
        logger.exception(e)
        errors.extend([
            'Internal error',
        ])
    logger.debug(json.dumps(errors))
    return ApiResponse({
        'success': len(errors) is 0,
        'errors': errors
    })


@csrf_exempt
@require_http_methods(['POST'])
def vote_send(request):
    talk_id = request.JSON.get('talk', None)
    if talk_id is None:
        raise ApiException('No talk set!', 400)
    try:
        talk = Talk.objects.get(id=talk_id)
    except Talk.DoesNotExist:
        raise ApiException('Invalid talk set!', 404)
    rating = request.JSON.get('rating', None)
    if rating is None:
        raise ApiException('No rating set!', 400)
    try:
        rating = max(0, min(5, int(rating)))
    except ValueError:
        raise ApiException('Invalid rating set!', 404)
    badge = utils.get_badge(request)
    Vote.objects.update_or_create(badge=badge, talk=talk, defaults=dict(
        rating=rating,
    ))
    return ApiResponse(status=204)


@csrf_exempt
@require_http_methods(['GET'])
def vote_get(request):
    key = request.META.get('HTTP_AUTHORIZATION', None)
    if key is None:
        raise AuthenticationError('No API key specified!')
    try:
        api_key = ApiKey.objects.get(key=key)
    except ApiKey.DoesNotExist:
        raise AuthenticationError('Invalid API key specified!')
    try:
        api_key.scopes.get(id=SCOPE_VOTES)
    except Scope.DoesNotExist:
        raise AuthenticationError('Invalid API key scope!')
    return ApiResponse(dict(
        votes=[
            dict(
                talk=dict(
                    id=talk.agenda_id,
                    slug=talk.slug,
                ),
                **(
                    lambda votes: dict(
                        rating=statistics.mean(votes) if len(votes) > 0 else 0,
                        ratings=len(votes),
                    )
                )([vote.rating for vote in Vote.objects.filter(talk=talk)])
            )
            for talk in Talk.objects.all()
        ],
    ))


@csrf_exempt
@require_http_methods(['POST'])
def message_send(request):
    receiver_id = request.JSON.get('receiver', None)
    if receiver_id is None:
        raise ApiException('No receiver set!', 400)
    try:
        receiver = Badge.objects.get(id=receiver_id)
    except Badge.DoesNotExist:
        raise ApiException('Invalid receiver set!', 404)
    message = request.JSON.get('message', None)
    if message is None:
        raise ApiException('No message set!', 400)
    try:
        message = message[:255]
    except ValueError:
        raise ApiException('Invalid message set!', 400)
    sender = utils.get_badge(request)
    Message.objects.create(sender=sender, receiver=receiver, message=message)
    return ApiResponse(status=204)


@csrf_exempt
@require_http_methods(['GET'])
def message_get(request):
    badge = utils.get_badge(request)
    messages = Message.objects.filter(receiver=badge, read=False).order_by('sent')
    if len(messages) is 0:
        return ApiResponse(status=204)
    message = messages[0]
    message.read = True
    message.save()
    return ApiResponse(dict(
        sender=dict(
            id=message.sender.id,
            name=message.sender.name,
        ),
        receiver=dict(
            id=message.receiver.id,
            name=message.receiver.name,
        ),
        message=message.message,
        sent=message.sent,
    ))


@csrf_exempt
@require_http_methods(['POST'])
def post_send(request):
    content = request.JSON.get('content', None)
    if content is None:
        raise ApiException('No message set!', 400)
    try:
        content = content[:255]
    except ValueError:
        raise ApiException('Invalid message set!', 400)
    sender = utils.get_badge(request)
    Post.objects.create(sender=sender, content=content)
    return ApiResponse(status=204)


@csrf_exempt
@require_http_methods(['GET'])
def post_get(request):
    key = request.META.get('HTTP_AUTHORIZATION', None)
    try:
        limit = int(request.GET.get('limit', None))
    except ValueError:
        limit = 10
    if key is None:
        raise AuthenticationError('No API key specified!')
    try:
        api_key = ApiKey.objects.get(key=key)
    except ApiKey.DoesNotExist:
        raise AuthenticationError('Invalid API key specified!')
    try:
        api_key.scopes.get(id=SCOPE_POSTS)
    except Scope.DoesNotExist:
        raise AuthenticationError('Invalid API key scope!')
    return ApiResponse(dict(
        posts=[
            dict(
                sender=dict(
                    id=post.sender.id,
                    name=post.sender.name,
                ),
                content=post.content,
            )
            for post in Post.objects.all().order_by('-created_at')[:limit]
        ],
    ))

@csrf_exempt
@require_http_methods(['GET'])
def export_all(request):
    key = request.META.get('HTTP_AUTHORIZATION', None)
    images = request.GET.get('images', None) is not None
    if key is None:
        raise AuthenticationError('No API key specified!')
    try:
        api_key = ApiKey.objects.get(key=key)
    except ApiKey.DoesNotExist:
        raise AuthenticationError('Invalid API key specified!')
    try:
        api_key.scopes.get(id=SCOPE_EXPORT)
    except Scope.DoesNotExist:
        raise AuthenticationError('Invalid API key scope!')
    return ApiResponse(dict(
        badges=[
            dict(
                id=badge.id,
                name=badge.name,
                image=badge.render().decode('ascii') if images else None,
            )
            for badge in Badge.objects.all()
        ],
    ))


@csrf_exempt
@require_http_methods(['GET'])
def export_single(request):
    key = request.META.get('HTTP_AUTHORIZATION', None)
    id = request.GET.get('id', None)
    if key is None:
        raise AuthenticationError('No API key specified!')
    try:
        api_key = ApiKey.objects.get(key=key)
    except ApiKey.DoesNotExist:
        raise AuthenticationError('Invalid API key specified!')
    try:
        api_key.scopes.get(id=SCOPE_EXPORT)
    except Scope.DoesNotExist:
        raise AuthenticationError('Invalid API key scope!')
    if id is None:
        raise ApiException('Missing id!', status=400)
    try:
        badge = Badge.objects.get(id=id)
    except Badge.DoesNotExist:
        raise ApiException('Invalid id!', status=400)
    return ApiResponse(dict(
        id=badge.id,
        name=badge.name,
        mac=badge.mac,
        image=badge.render().decode('ascii'),
    ))




