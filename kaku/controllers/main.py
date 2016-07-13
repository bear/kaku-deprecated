# -*- coding: utf-8 -*-
"""
:copyright: (c) 2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""
import uuid
import urllib

import ninka
import requests

from flask import Blueprint, current_app, request, redirect, render_template, jsonify
from flask_wtf import Form
from wtforms import TextField, HiddenField
from urlparse import ParseResult
from kaku.tools import checkAccessToken, validURL, clearAuth
from kaku.micropub import micropub
from kaku.mentions import mention

from bearlib.tools import baseDomain


main = Blueprint('main', __name__)

class MPTokenForm(Form):
    me           = TextField('me', validators=[])
    scope        = TextField('scope', validators=[])
    redirect_uri = HiddenField('redirect_uri', validators=[])
    client_id    = HiddenField('client_id', validators=[])
    state        = HiddenField('state', validators=[])

def request_wants_json():
    best = request.accept_mimetypes \
        .best_match(['application/json', 'text/html'])
    return best == 'application/json' and \
        request.accept_mimetypes[best] > \
        request.accept_mimetypes['text/html']

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
                    return ('Webmention created for %s' % target, 201, {'Location': target})
                else:
                    if current_app.config['VOUCH_REQUIRED'] and not vouched:
                        return 'Vouch required for webmention', 449
                    else:
                        return 'Webmention is invalid', 400
            else:
                return 'Webmention target was not found', 400
        else:
            return 'Webmention target is not valid', 400

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
                properties = {}
                for key in ('h', 'name', 'summary', 'content', 'published', 'updated',
                            'slug', 'location', 'syndication', 'syndicate-to',
                            'in-reply-to', 'repost-of', 'like-of', 'bookmark-of'):
                    properties[key] = request.form.get(key)
                for key in request.form.keys():
                    if key.lower().startswith('mp-'):
                        properties[key.lower()] = request.form.get(key)
                properties['category'] = request.form.getlist('category[]')
                properties['html']     = request.form.getlist('content[html]')
                for key in properties:
                    current_app.logger.info('    %s = [%s]' % (key, properties[key]))
                data = { 'domain':     domain,
                         'app':        client_id,
                         'scope':      scope,
                         'properties': properties
                       }
                return micropub(request.method, data)
            else:
                return 'Unauthorized', 403
        elif request.method == 'GET':
            q = request.args.get('q')
            current_app.logger.info('GET q [%s]' % q)
            if q is not None and q.lower() == 'syndicate-to':
                if request_wants_json:
                    resp             = jsonify({ 'syndicate-to': current_app.config['SITE_SYNDICATE'] })
                    resp.status_code = 200
                    return resp
                else:
                    return ('&'.join(map('syndicate-to[]={0}'.format, map(urllib.quote, current_app.config['SITE_SYNDICATE']))),
                            200, {'Content-Type': 'application/x-www-form-urlencoded'})
            else:
                return 'not implemented', 501
        else:
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

@main.route('/access', methods=['GET', 'POST'])
def handleAccessToken():
    current_app.logger.info('handleAccessToken [%s]' % request.method)

    form = MPTokenForm(me=current_app.config['BASEURL'],
                       client_id=current_app.config['CLIENT_ID'],
                       redirect_uri='%s/access' % current_app.config['BASEURL'],
                       from_uri='%s/access' % current_app.config['BASEURL'],
                       scope='post')

    if form.validate_on_submit():
        me            = 'https://%s/' % baseDomain(form.me.data, includeScheme=False)
        authEndpoints = ninka.indieauth.discoverAuthEndpoints(me)

        if 'authorization_endpoint' in authEndpoints:
            authURL = None
            for url in authEndpoints['authorization_endpoint']:
                authURL = url
                break
            if authURL is not None:
                url = ParseResult(authURL.scheme,
                                  authURL.netloc,
                                  authURL.path,
                                  authURL.params,
                                  urllib.urlencode({ 'me':            me,
                                                     'redirect_uri':  form.redirect_uri.data,
                                                     'client_id':     form.client_id.data,
                                                     'scope':         form.scope.data,
                                                     'response_type': 'id'
                                                   }),
                                  authURL.fragment).geturl()

                key  = 'access-%s' % me
                data = current_app.dbRedis.hgetall(key)
                if data and 'token' in data:  # clear any existing auth data
                    current_app.dbRedis.delete('token-%s' % data['token'])
                    current_app.dbRedis.hdel(key, 'token')
                current_app.dbRedis.hset(key, 'auth_url',     ParseResult(authURL.scheme, authURL.netloc, authURL.path, '', '', '').geturl())
                current_app.dbRedis.hset(key, 'redirect_uri', form.redirect_uri.data)
                current_app.dbRedis.hset(key, 'client_id',    form.client_id.data)
                current_app.dbRedis.hset(key, 'scope',        form.scope.data)
                current_app.dbRedis.expire(key, current_app.config['AUTH_TIMEOUT'])  # expire in N minutes unless successful
                current_app.logger.info('redirecting to [%s]' % url)
                return redirect(url)
        else:
            return 'insert fancy no auth endpoint found error message here', 403
    else:
        me    = request.args.get('me')
        code  = request.args.get('code')
        current_app.logger.info('me [%s] code [%s]' % (me, code))

        if code is None:
            templateContext = {}
            templateContext['form'] = form
            return render_template('mptoken.jinja', **templateContext)
        else:
            current_app.logger.info('getting data to validate auth code')
            key  = 'access-%s' % me
            data = current_app.dbRedis.hgetall(key)
            if data:
                current_app.logger.info('calling [%s] to validate code' % data['auth_url'])
                r = ninka.indieauth.validateAuthCode(code=code,
                                                     client_id=data['client_id'],
                                                     redirect_uri=data['redirect_uri'],
                                                     validationEndpoint=data['auth_url'])
                current_app.logger.info('validateAuthCode returned %s' % r['status'])
                if r['status'] == requests.codes.ok:
                    current_app.logger.info('login code verified')
                    token = str(uuid.uuid4())

                    current_app.dbRedis.hset(key, 'code',  code)
                    current_app.dbRedis.hset(key, 'token', token)
                    current_app.dbRedis.expire(key, current_app.config['AUTH_TIMEOUT'])
                    current_app.dbRedis.set('token-%s' % token, key)
                    current_app.dbRedis.expire('token-%s' % code, current_app.config['AUTH_TIMEOUT'])
                    return 'Access Token: %s' % token, 200
                else:
                    current_app.logger.info('login invalid')
                    clearAuth()
                    return 'Invalid', 401
            else:
                current_app.logger.info('nothing found for [%s]' % me)
                clearAuth()
                return 'Invalid', 401
