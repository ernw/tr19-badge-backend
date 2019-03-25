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
import json

from django.conf.urls import url
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.dateparse import parse_date
from django.utils.html import format_html

from badge.forms import ImportTalksForm
from badge.models import Badge, AuthCode, Setting, Vote, Talk, Track, ApiKey, Scope, Day, Message, Post
from badge.models.app import App


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('id', 'mac', 'name')
    list_display_links = ('id', )
    fields = ('id', 'mac', 'secret', 'name', 'image', 'image_tag')
    readonly_fields = ('id', 'mac', 'secret', 'image_tag')
    search_fields = ('id', 'mac', 'name')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def image_tag(self, obj):
        return format_html(
            '<img src="data:image/png;base64,{}" />',
            obj.render().decode('ascii')
        )
    image_tag.short_description = 'Image'


@admin.register(AuthCode)
class AuthCodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'badge', 'long_lived', 'expired')
    list_display_links = ('id', )
    fields = ('id', 'badge', 'long_lived', 'expired', 'last_used')
    readonly_fields = ('id', 'badge', 'long_lived', 'expired', 'last_used')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(App)
class AppAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'title', 'version')
    list_display_links = ('id', )
    fields = ('name', 'title', 'blob')
    readonly_fields = ('version', )

    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return True


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'badge')
    list_display_links = ('key', )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'badge', 'talk')
    list_display_links = ('id', )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'receiver', 'read', 'sent')
    list_display_links = ('id', )
    fields = ('id', 'sender', 'receiver', 'sent', 'read', 'message')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'created_at')
    list_display_links = ('id', )
    fields = ('id', 'sender', 'created_at', 'content')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Day)
class DayAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    list_display_links = ('id', 'name')

    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return True


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'day')
    list_display_links = ('id', 'name')

    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return True


@admin.register(Talk)
class TalkAdmin(admin.ModelAdmin):
    change_list_template = 'admin/badge/talk/change_list.html'
    import_template = 'admin/badge/talk/import.html'

    list_display = ('id', 'track', 'title')
    list_display_links = ('id', 'title')
    # fields = ('id', 'title', 'speaker', 'time')
    readonly_fields = ('rating', )

    list_filter = ('track', 'speaker')
    actions = ['import_talks']

    def get_urls(self):
        urls = super(TalkAdmin, self).get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        return [
            url(r'import/', self.admin_site.admin_view(self.import_talks), name='%s_%s_import' % info),
        ] + urls

    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def import_talks(self, request):
        messages.warning(request, 'Importing an agenda will delete all previous talks!')
        if request.method == 'POST':
            form = ImportTalksForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    data = json.load(request.FILES['file'])
                    days = data['schedule']['conference']['days']
                    start = form.cleaned_data['start']
                    end = form.cleaned_data['end'] + 1
                    ok = True
                    if start > len(days):
                        messages.error('Start cannot be greater than the number of days in the schedule')
                        ok = False
                    if end > len(days):
                        messages.error('End cannot be greater than the number of days in the schedule')
                        ok = False
                    if start > end:
                        messages.error('Start cannot be greater than end')
                        ok = False
                    if ok:
                        Day.objects.all().delete()
                        for i, day in enumerate(days[start:end]):
                            # Create day
                            d = Day.objects.create(date=parse_date(day['date']), name='Day {}'.format(i + 1))
                            for room in day['rooms'].keys():
                                for talk in day['rooms'][room]:
                                    r, created = Track.objects.get_or_create(name=room, day=d)
                                    t = Talk.objects.create(
                                        title=talk['title'],
                                        speaker=', '.join(person['name'] for person in talk['persons']),
                                        agenda_id=talk['id'],
                                        slug=talk['slug'][:10],
                                        track=r,
                                        time=talk['start'],
                                    )
                        return redirect('/admin/{}/{}/'.format(self.model._meta.app_label, self.model._meta.model_name))
                except json.decoder.JSONDecodeError as jde:
                    messages.error(request, str(jde))
            else:
                for error in form.errors:
                    messages.error(request, error)
        context = dict(
            # Include common variables for rendering the admin template.
            self.admin_site.each_context(request),
            title='Import talks',
            form=ImportTalksForm(),
            opts=self.model._meta,

        )
        return TemplateResponse(request, self.import_template, context)


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ('key', 'scopes_list')
    list_display_links = ('key',)
    readonly_fields = ('key', )

    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def scopes_list(self, obj):
        return ', '.join([scope.__str__() for scope in obj.scopes.all()])


@admin.register(Scope)
class ScopeAdmin(admin.ModelAdmin):
    list_display = ('id', 'description')
    list_display_links = ('id', )

    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return True
