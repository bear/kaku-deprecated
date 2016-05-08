# -*- coding: utf-8 -*-
"""
:copyright: (c) 2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""
import uuid
import urllib

import ninka
import requests

from flask import Blueprint, current_app, request, redirect

from kaku.tools import checkAccessToken, validURL
from kaku.micropub import micropub
from kaku.webmentions import mention

from bearlib.tools import baseDomain


main = Blueprint('main', __name__)

@main.route('/webmention', methods=['POST'])
def handleWebmention():
    current_app.logger.info('handleWebmention [%s]' % request.method)
    if request.method == 'POST':
        valid  = False
        source = request.form.get('source')
        target = request.form.get('target')
        vouch  = request.form.get('vouch')
        current_app.logger.info('source: %s target: %s vouch %s' % (source, target, vouch))
        if current_app.config['BASEROUTE'] in target:
            valid = validURL(target)
            current_app.logger.info('valid? %s' % valid)
            if valid == requests.codes.ok:
                valid, vouched = mention(source, target, vouch)
                if valid:
                    return redirect(target)
                else:
                    if current_app.config['VOUCH_REQUIRED'] and not vouched:
                        return 'Vouch required for webmention', 449
                    else:
                        return 'Webmention is invalid', 400
            else:
                return 'invalid post', 404
        else:
            return 'invalid post', 404

@main.route('/micropub', methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'])
def handleMicroPub():
    current_app.logger.info('handleMicroPub [%s]' % request.method)
    # form = MicroPubForm()

    access_token = request.headers.get('Authorization')
    if access_token:
        access_token = access_token.replace('Bearer ', '')
    me, client_id, scope = checkAccessToken(access_token)
    current_app.logger.info('[%s] [%s] [%s] [%s]' % (access_token, me, client_id, scope))

    if me is None or client_id is None:
        return ('Access Token missing', 401, {})
    else:
        if request.method == 'POST':
                domain   = baseDomain(me, includeScheme=False)
                idDomain = baseDomain(current_app.config['CLIENT_ID'], includeScheme=False)
                if domain == idDomain and checkAccessToken(access_token):
                    data = { 'domain': domain,
                             'app':    client_id,
                             'scope':  scope
                           }
                    for key in ('h', 'name', 'summary', 'content', 'published', 'updated',
                                'category', 'slug', 'location', 'syndication', 'syndicate-to',
                                'in-reply-to', 'repost-of', 'like-of'):
                        data[key] = request.form.get(key)
                        current_app.logger.info('    %s = [%s]' % (key, data[key]))
                    for key in request.form.keys():
                        if key not in data:
                            data[key] = request.form.get(key)
                            current_app.logger.info('    %s = [%s]' % (key, data[key]))
                    return micropub(request.method, data)
                else:
                    return 'Unauthorized', 403
        elif request.method == 'GET':
            # add support for /micropub?q=syndicate-to
            return 'not implemented', 501

@main.route('/token', methods=['POST', 'GET'])
def handleToken():
    current_app.logger.info('handleToken [%s]' % request.method)

    if request.method == 'GET':
        access_token = request.headers.get('Authorization')
        if access_token:
            access_token = access_token.replace('Bearer ', '')
        else:
            access_token
        me, client_id, scope = checkAccessToken(access_token)

        if me is None or client_id is None:
            return ('Token is not valid', 400, {})
        else:
            params = { 'me':        me,
                       'client_id': client_id,
                     }
            if scope is not None:
                params['scope'] = scope
            return (urllib.urlencode(params), 200, {'Content-Type': 'application/x-www-form-urlencoded'})

    elif request.method == 'POST':
        code         = request.form.get('code')
        me           = request.form.get('me')
        redirect_uri = request.form.get('redirect_uri')
        client_id    = request.form.get('client_id')
        state        = request.form.get('state')

        current_app.logger.info('    code         [%s]' % code)
        current_app.logger.info('    me           [%s]' % me)
        current_app.logger.info('    client_id    [%s]' % client_id)
        current_app.logger.info('    state        [%s]' % state)
        current_app.logger.info('    redirect_uri [%s]' % redirect_uri)

        r = ninka.indieauth.validateAuthCode(code=code,
                                             client_id=me,
                                             state=state,
                                             redirect_uri=redirect_uri)
        if r['status'] == requests.codes.ok:
            current_app.logger.info('token request auth code verified')
            scope = r['response']['scope']
            key   = 'app-%s-%s-%s' % (me, client_id, scope)
            token = current_app.dbRedis.get(key)
            if token is None:
                token     = str(uuid.uuid4())
                token_key = 'token-%s' % token
                current_app.dbRedis.set(key, token)
                current_app.dbRedis.set(token_key, key)

            current_app.logger.info('  token generated for [%s] : [%s]' % (key, token))
            params = { 'me': me,
                       'scope': scope,
                       'access_token': token
                     }
            return (urllib.urlencode(params), 200, {'Content-Type': 'application/x-www-form-urlencoded'})
