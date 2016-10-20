# -*- coding: utf-8 -*-
"""
:copyright: (c) 2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""
import os
import uuid
import json
import urllib

import ninka
import requests

from flask import Blueprint, current_app, request, redirect, render_template, jsonify
from werkzeug import secure_filename
from flask_wtf import Form
from wtforms import TextField, HiddenField
from urlparse import ParseResult, urlparse
from kaku.tools import validateAccessToken, validateDomain, validURL, clearAuth
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
        source = request.form.get('source')
        target = request.form.get('target')
        vouch  = request.form.get('vouch')
        current_app.logger.info('source: %s target: %s vouch %s' % (source, target, vouch))
        if current_app.config['BASEROUTE'] in target and validURL(target) == requests.codes.ok:
            valid, vouched = mention(source, target, vouch)
            if valid:
                return ('Webmention created for %s' % target, 201, {'Location': target})
            else:
                if current_app.config['VOUCH_REQUIRED'] and not vouched:
                    return 'Vouch required for webmention', 449
                else:
                    return 'Webmention is invalid', 400
        else:
            return 'Webmention target is not valid', 400

@main.route('/media', methods=['GET', 'POST'])
def handleMedia():
    # https://www.w3.org/TR/2016/CR-micropub-20160816/#media-endpoint
    current_app.logger.info('handleMedia [%s]' % request.method)
    me, client_id, scope, allowed = validateAccessToken(request.headers.get('Authorization'))
    if not allowed:
        return 'Not allowed', 401
    domain = baseDomain(me, includeScheme=False)
    if request.method == 'POST' and validateDomain(domain):
        item     = request.files.get('file')
        filename = secure_filename(item.filename)

        # TODO replace this with a plugin callable to retrieve what the file path and url should be
        item.save(os.path.join(current_app.config['MEDIA_FILES'], filename))
        location = '%s%s%s/%s' % (current_app.config['BASEURL'],
                                  current_app.config['BASEROUTE'],
                                  current_app.config['MEDIA_DIR'],
                                  filename)
        return ('Media successful for %s' % location, 201, {'Location': location})
    else:
        return 'Invalid request', 400

_property_keys = ( 'name', 'summary', 'published', 'updated', 'category',
                   'slug', 'location', 'syndication', 'syndicate-to',
                   'in-reply-to', 'repost-of', 'like-of', 'bookmark-of' )

@main.route('/micropub', methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'])
def handleMicroPub():
    current_app.logger.info('handleMicroPub [%s]' % request.method)
    me, client_id, scope, allowed = validateAccessToken(request.headers.get('Authorization'))
    if not allowed:
        return 'Not allowed', 401
    domain = baseDomain(me, includeScheme=False)
    if request.method == 'POST' and validateDomain(domain):
        data = { 'domain': domain,
                 'app':    client_id,
                 'scope':  scope,
               }
        payload = request.get_json()
        properties = { 'type':   'h-entry',
                       'action': 'create',
                     }
        for _key in _property_keys:
            properties[_key] = None
        for _key in ('content', 'html', 'category', 'photo', 'photo_files'):
            properties[_key] = []

        for key in ('photo', 'photo[]'):
            items = request.files.getlist(key)
            for item in items:
                filename = secure_filename(item.filename)
                properties['photo_files'].append(filename)
                # TODO rectify why we save files here to uploads dir but media endpoint doesn't
                item.save(os.path.join(current_app.config['UPLOADS'], filename))

        # form encoded
        if payload is None:
            properties['type'] = 'h-%s' % request.form.get('h')
            for key, value in request.form.iteritems(multi=True):
                key = key.lower()
                if key == 'category':
                    properties[key].append(value)
                elif key == 'photo':
                    properties[key].append((request.form.get(key), ''))
                elif key == 'content':
                    properties[key] = request.form.get(key).replace('\r\n', '\n').split('\n')
                else:
                    properties[key] = value
                current_app.logger.info('      %s --> %s' % (key, value))

            # get any photos-as-array values
            properties['photo'] += list(zip(request.form.getlist('photo[value]'),
                                            request.form.getlist('photo[alt]')))

            # get any categorties as array values
            for key, value in request.form.iteritems(multi=True):
                if key.lower().startswith('category['):
                    properties['category'].append(value)

            properties['html'] = request.form.getlist('content[html]')
        else:
            # json data
            if 'type' in payload:
                properties['type'] = payload['type'][0]
            if 'action' in payload:
                for key in ('action', 'url', 'replace', 'add', 'delete'):
                    if key in payload:
                        properties[key] = payload[key]
            if 'properties' in payload:
                for key in payload['properties']:
                    value           = payload['properties'][key]
                    properties[key] = value
                    current_app.logger.info('      %s ==> %s' % (key, value))

            if type(properties['content']) is dict:
                if 'html' in properties['content']:
                    properties['html']    = properties['content']['html']
                    properties['content'] = []

            if 'photo' in properties:
                photos = []
                for item in properties['photo']:
                    alt = ''
                    if type(item) is dict:
                        photo = item['value']
                        if 'alt' in item:
                            alt = item['alt']
                    else:
                        photo = item
                    photos.append((photo, alt))
                properties['photo'] = photos

        data['properties'] = properties
        for key in data['properties']:
            current_app.logger.info('    %s = %s' % (key, data['properties'][key]))
        return micropub(request.method, data)
    elif request.method == 'GET':
        # https://www.w3.org/TR/2016/CR-micropub-20160816/#querying
        query = request.args.get('q')
        current_app.logger.info('query [%s]' % query)
        if query is not None:
            query      = query.lower()
            respJson   = { 'media-endpoint': current_app.config['MEDIA_ENDPOINT'],
                           'syndicate-to': current_app.config['SITE_SYNDICATE'] }
            respParam  = '&'.join(map('syndicate-to[]={0}'.format, map(urllib.quote, current_app.config['SITE_SYNDICATE'])))
            respParam += '&media-endpoint=%s' % (current_app.config['MEDIA_ENDPOINT'])
            if query == 'config':
                # https://www.w3.org/TR/2016/CR-micropub-20160816/#configuration
                if request_wants_json:
                    resp             = jsonify(respJson)
                    resp.status_code = 200
                    return resp
                else:
                    return (respParam, 200, {'Content-Type': 'application/x-www-form-urlencoded'})
            elif query == 'syndicate-to':
                # https://www.w3.org/TR/2016/CR-micropub-20160816/#syndication-targets
                if request_wants_json:
                    resp             = jsonify(respJson)
                    resp.status_code = 200
                    return resp
                else:
                    return (respParam, 200, {'Content-Type': 'application/x-www-form-urlencoded'})
            elif query == 'source':
                # https://www.w3.org/TR/2016/CR-micropub-20160816/#source-content
                url        = request.args.get('url')
                properties = []
                for key in ('properties', 'properties[]'):
                    item = request.args.getlist(key)
                    if len(item) > 0:
                        properties += item
                current_app.logger.info('url: %s properties: %d %s' % (url, len(properties), properties))

                # "If no properties are specified, then the response must include all properties,
                #  as well as a type property indicating the vocabulary of the post."
                # so this is a list of properties the code currently handles
                if len(properties) == 0:
                    properties = ['type', 'category', 'content', 'published']

                targetPath = urlparse(url).path
                pathItems  = targetPath.split('.')
                current_app.logger.info('[%s] %s' % (targetPath, pathItems))

                # normalize the url target to remove any extension
                if pathItems[-1].lower() == 'html':
                    targetPath = '.'.join(pathItems[:-1])
                slug       = targetPath.replace(current_app.config['BASEROUTE'], '')
                targetFile = '%s.json' % os.path.join(current_app.config['SITE_CONTENT'], slug)
                current_app.logger.info('targetFile: %s' % targetFile)
                if os.path.exists(targetFile):
                    with open(targetFile, 'r') as h:
                        post = json.load(h)
                    respJson = { "type": ["h-entry"], "properties": {} }
                    if 'published' in properties:
                        respJson['properties']['published'] = [ post['published'] ]
                    if 'category' in properties and len(post['tags']) > 0:
                        respJson['properties']['category'] = post['tags'].split(',')
                    if 'content' in properties:
                        respJson['properties']['content'] = post['content'].split('\n')
                    current_app.logger.info(json.dumps(respJson))
                    resp = jsonify(respJson)
                    resp.status_code = 200
                    return resp
                else:
                    return 'not found', 404
            else:
                return 'not implemented', 501
        else:
            return 'not implemented', 501
    else:
        return 'not implemented', 501

@main.route('/token', methods=['POST', 'GET'])
def handleToken():
    current_app.logger.info('handleToken [%s]' % request.method)
    if request.method == 'GET':
        me, client_id, scope, allowed = validateAccessToken(request.headers.get('Authorization'))
        if not allowed:
            return 'Not allowed', 401
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
                    current_app.dbRedis.set('token-%s' % token, 'app-%s-%s-%s' % (me, data['client_id'], data['scope']))
                    current_app.dbRedis.expire('token-%s' % token, current_app.config['AUTH_TIMEOUT'])
                    app_key = 'app-%s-%s-%s' % (me, data['client_id'], data['scope'])
                    current_app.dbRedis.hset(app_key, 'auth_url',     data['auth_url'])
                    current_app.dbRedis.hset(app_key, 'redirect_uri', data['redirect_uri'])
                    current_app.dbRedis.hset(app_key, 'client_id',    data['client_id'])
                    current_app.dbRedis.hset(app_key, 'scope',        data['scope'])
                    current_app.dbRedis.expire(app_key, current_app.config['AUTH_TIMEOUT'])  # expire in N minutes unless successful

                    return 'Access Token: %s' % token, 200
                else:
                    current_app.logger.info('login invalid')
                    clearAuth()
                    return 'Invalid', 401
            else:
                current_app.logger.info('nothing found for [%s]' % me)
                clearAuth()
                return 'Invalid', 401
