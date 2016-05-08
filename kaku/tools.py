# -*- coding: utf-8 -*-
"""
:copyright: (c) 2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""

import os
import json
import uuid
import requests

from urlparse import urlparse

from flask import current_app, session


def kakuEvent(eventType, eventAction, eventData):
    """Publish a Kaku event.

    A Kaku event is used to allow async handling of events
    from web requests.

    Event Types: mention, post, login
    Event Actions: created, updated, deleted
    Event Data: a dictionary of items relevant to the event

    The event is stored in the location key generated and that
    key is then published to the event queue.
    """
    key  = 'kaku-event::%s::%s::%s' % (eventType, eventAction, str(uuid.uuid4()))
    data = { 'type':   eventType,
             'action': eventAction,
             'data':   eventData,
             'key':    key
           }
    current_app.dbRedis.set(key, json.dumps(data))
    current_app.dbRedis.publish('kaku', key)

def clearAuth():
    if 'indieauth_token' in session:
        if current_app.dbRedis is not None:
            key = current_app.dbRedis.get('token-%s' % session['indieauth_token'])
            if key:
                current_app.dbRedis.delete(key)
                current_app.dbRedis.delete('token-%s' % session['indieauth_token'])
    session.pop('indieauth_token', None)
    session.pop('indieauth_scope', None)
    session.pop('indieauth_id',    None)

def checkAuth():
    authed       = False
    indieauth_id = None
    if 'indieauth_id' in session and 'indieauth_token' in session:
        current_app.logger.info('session cookie found')
        indieauth_id    = session['indieauth_id']
        indieauth_token = session['indieauth_token']
        if current_app.dbRedis is not None:
            key = current_app.dbRedis.get('token-%s' % indieauth_token)
            if key:
                data = current_app.dbRedis.hgetall(key)
                if data and data['token'] == indieauth_token:
                    authed = True
    return authed, indieauth_id

def checkAccessToken(access_token):
    if access_token is not None and current_app.dbRedis is not None:
        key = current_app.dbRedis.get('token-%s' % access_token)
        if key:
            data      = key.split('-')
            me        = data[1]
            client_id = data[2]
            scope     = data[3]
            current_app.logger.info('access token valid [%s] [%s] [%s]' % (me, client_id, scope))
            return me, client_id, scope
        else:
            return None, None, None
    else:
        return None, None, None

def validURL(targetURL):
    """Validate the target URL exists by making a HEAD request for it
    """
    result = 404
    try:
        r = requests.head(targetURL)
        result = r.status_code
    except:
        result = 404
    return result

def extractHCard(mf2Data):
    result = { 'name': '',
               'url':  '',
             }
    if 'items' in mf2Data:
        for item in mf2Data['items']:
            if 'type' in item and 'h-card' in item['type']:
                result['name'] = item['properties']['name']
                if 'url' in item['properties']:
                    result['url'] = item['properties']['url']
    return result

def generateSafeName(sourceURL):
    urlData = urlparse(sourceURL)
    result  = '%s_%s.mention' % (urlData.netloc, urlData.path.replace('/', '_'))
    return result

def generateMentionName(targetURL, vouched, cfg):
    urlData     = urlparse(targetURL)
    urlPaths    = urlData.path.split('/')
    basePath    = '/'.join(urlPaths[2:-1])
    mentionPath = os.path.join(cfg.paths.content, 'content', basePath)
    mentionSlug = urlPaths[-1]
    nMax        = 0

    if vouched:
        mentionExt = '.mention'
    else:
        mentionExt = '.mention_notvouched'

    for f in os.listdir(mentionPath):
        if f.endswith(mentionExt) and f.startswith(mentionSlug):
            try:
                n = int(f.split('.')[-2])
            except:
                n = 0
            if n > nMax:
                nMax = n
    return os.path.join(mentionPath, '%s.%03d%s' % (mentionSlug, nMax + 1, mentionExt))
