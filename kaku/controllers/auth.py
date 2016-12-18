# -*- coding: utf-8 -*-
"""
:copyright: (c) 2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""

import uuid
import urllib

import requests
import ninka

from flask import Blueprint, current_app, session, render_template, redirect, request
from flask_wtf import Form
from wtforms import TextField, HiddenField
from wtforms.validators import Required

from kaku.tools import clearAuth, baseDomain

try:
    # python 3
    from urllib.parse import ParseResult
except ImportError:
    from urlparse import ParseResult


auth = Blueprint('auth', __name__)

class LoginForm(Form):
    me           = TextField('me', validators=[ Required() ])
    client_id    = HiddenField('client_id')
    redirect_uri = HiddenField('redirect_uri')
    from_uri     = HiddenField('from_uri')

class PubishForm(Form):
    h            = TextField('h', validators=[])
    content      = TextField('content', validators=[])
    title        = TextField('title', validators=[])
    published    = TextField('published', validators=[])
    inreplyto    = TextField('in-reply-to', validators=[])
    syndicateto  = TextField('syndicate-to', validators=[])


@auth.route('/logout', methods=['GET'])
def handleLogout():
    current_app.logger.info('handleLogout [%s]' % request.method)
    clearAuth()
    return redirect('/')

@auth.route('/login', methods=['GET', 'POST'])
def handleLogin():
    current_app.logger.info('handleLogin [%s]' % request.method)

    me          = None
    redirectURI = '%s/success' % current_app.config['BASEURL']
    fromURI     = request.args.get('from_uri')

    current_app.logger.info('redirectURI [%s] fromURI [%s]' % (redirectURI, fromURI))
    form = LoginForm(me='',
                     client_id=current_app.config['CLIENT_ID'],
                     redirect_uri=redirectURI,
                     from_uri=fromURI)

    if form.validate_on_submit():
        current_app.logger.info('me [%s]' % form.me.data)

        me            = 'https://%s/' % baseDomain(form.me.data, includeScheme=False)
        scope         = ''
        authEndpoints = ninka.indieauth.discoverAuthEndpoints(me)

        if 'authorization_endpoint' in authEndpoints:
            authURL = None
            for url in authEndpoints['authorization_endpoint']:
                authURL = url
                break
            if authURL is not None:
                if me == current_app.config['BASEURL']:
                    scope = 'post update delete'
                url = ParseResult(authURL.scheme,
                                  authURL.netloc,
                                  authURL.path,
                                  authURL.params,
                                  urllib.urlencode({ 'me':            me,
                                                     'redirect_uri':  form.redirect_uri.data,
                                                     'client_id':     form.client_id.data,
                                                     'scope':         scope,
                                                     'response_type': 'id'
                                                   }),
                                  authURL.fragment).geturl()
                if current_app.dbRedis is not None:
                    key  = 'login-%s' % me
                    data = current_app.dbRedis.hgetall(key)
                    if data and 'token' in data:  # clear any existing auth data
                        current_app.dbRedis.delete('token-%s' % data['token'])
                        current_app.dbRedis.hdel(key, 'token')
                    current_app.dbRedis.hset(key, 'auth_url',     ParseResult(authURL.scheme, authURL.netloc, authURL.path, '', '', '').geturl())
                    current_app.dbRedis.hset(key, 'from_uri',     form.from_uri.data)
                    current_app.dbRedis.hset(key, 'redirect_uri', form.redirect_uri.data)
                    current_app.dbRedis.hset(key, 'client_id',    form.client_id.data)
                    current_app.dbRedis.hset(key, 'scope',        scope)
                    current_app.dbRedis.expire(key, current_app.config['AUTH_TIMEOUT'])  # expire in N minutes unless successful
                current_app.logger.info('redirecting to [%s]' % url)
                return redirect(url)
        else:
            return 'insert fancy no auth endpoint found error message here', 403

    templateContext = {}
    templateContext['title'] = 'Sign In'
    templateContext['form']  = form
    return render_template('login.jinja', **templateContext)

@auth.route('/success', methods=['GET', ])
def handleLoginSuccess():
    current_app.logger.info('handleLoginSuccess [%s]' % request.method)
    scope = None
    me    = request.args.get('me')
    code  = request.args.get('code')
    current_app.logger.info('me [%s] code [%s]' % (me, code))

    if current_app.dbRedis is not None:
        current_app.logger.info('getting data to validate auth code')
        key  = 'login-%s' % me
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
                if 'scope' in r['response']:
                    scope = r['response']['scope']
                else:
                    scope = data['scope']
                from_uri = data['from_uri']
                token    = str(uuid.uuid4())

                current_app.dbRedis.hset(key, 'code',  code)
                current_app.dbRedis.hset(key, 'token', token)
                current_app.dbRedis.expire(key, current_app.config['AUTH_TIMEOUT'])
                current_app.dbRedis.set('token-%s' % token, key)
                current_app.dbRedis.expire('token-%s' % code, current_app.config['AUTH_TIMEOUT'])

                session['indieauth_token'] = token
                session['indieauth_scope'] = scope
                session['indieauth_id']    = me
            else:
                current_app.logger.info('login invalid')
                clearAuth()
        else:
            current_app.logger.info('nothing found for [%s]' % me)

    if scope:
        if from_uri:
            return redirect(from_uri)
        else:
            return redirect('/')
    else:
        return 'authentication failed', 403

@auth.route('/auth', methods=['GET', ])
def handleAuth():
    current_app.logger.info('handleAuth [%s]' % request.method)
    result = False
    if current_app.dbRedis is not None:
        token = request.args.get('token')
        if token is not None:
            me = current_app.dbRedis.get('token-%s' % token)
            if me:
                data = current_app.dbRedis.hgetall(me)
                if data and data['token'] == token:
                    result = True
    if result:
        return 'valid', 200
    else:
        clearAuth()
        return 'invalid', 403
