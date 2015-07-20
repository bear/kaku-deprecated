#!/usr/bin/env python

"""
:copyright: (c) 2015 by Mike Taylor
:license: MIT, see LICENSE for more details.

A Flask service to handle inbound HTML
events that IndieWeb Micropub requires.
"""

import os, sys
import re
import json
import uuid
import urllib
import logging
import datetime

# import pytz
import redis
import ninka
import ronkyuu
import requests

from bearlib.config import Config
from bearlib.events import Events
from bearlib.tools import baseDomain
from unidecode import unidecode
# from mf2py.parser import Parser
from dateutil.parser import parse
from urlparse import urlparse, ParseResult

from flask import Flask, request, redirect, render_template, session, flash
from flask.ext.wtf import Form
from wtforms import TextField, HiddenField, BooleanField
from wtforms.validators import Required


class LoginForm(Form):
    me           = TextField('me', validators = [ Required() ])
    client_id    = HiddenField('client_id')
    redirect_uri = HiddenField('redirect_uri')
    from_uri     = HiddenField('from_uri')

class MicroPubForm(Form):
    h            = TextField('h', validators = [])
    content      = TextField('content', validators = [])
    title        = TextField('title', validators = [])
    published    = TextField('published', validators = [])
    slug         = TextField('slug', validators = [])
    inreplyto    = TextField('in-reply-to', validators = [])
    syndicateto  = TextField('syndicate-to', validators = [])

class TokenForm(Form):
    # app_id     = TextField('app_id', validators = [ Required() ])
    # invalidate = BooleanField('invalidate')
    # app_token  = TextField('app_token')
    # client_id  = HiddenField('client_id')
    code         = TextField('code', validators = [])
    me           = TextField('me', validators = [])
    redirect_uri = TextField('redirect_uri', validators = [])
    client_id    = TextField('client_id', validators = [])
    state        = TextField('state', validators = [])


# check for uwsgi, use PWD if present or getcwd() if not
_uwsgi = __name__.startswith('uwsgi')
if _uwsgi:
    _ourPath    = os.getenv('PWD', None)
    _configFile = '/etc/kaku.cfg'
else:
    _ourPath    = os.getcwd()
    _configFile = os.path.join(_ourPath, 'kaku.cfg')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'foo'  # replaced downstream
cfg    = None
db     = None
events = None
templateContext = {}
templateCache   = {}

def getDomainConfig(domain=None):
    result = None
    if domain is not None:
        if domain not in templateCache:
            templateCache[domain] = Config()
            templateCache[domain].fromJson(config[domain])
        result = templateCache[domain]
    if result is None:
        result = Config()
    return result

def buildTemplateContext(config, domain):
    templateContext = {}
    domainConfig    = getDomainConfig(domain)
    for key in ('baseurl', 'title', 'meta'):
        if key in domainConfig:
            value = domainConfig[key]
        else:
            value = ''
        templateContext[key] = value

def clearAuth():
    if 'indieauth_token' in session:
        if db is not None:
            key = db.get('token-%s' % session['indieauth_token'])
            if key:
                db.delete(key)
                db.delete('token-%s' % session['indieauth_token'])
    session.pop('indieauth_token', None)
    session.pop('indieauth_scope', None)
    session.pop('indieauth_id',    None)

def checkAuth():
    authed        = False
    indieauth_id  = None
    if 'indieauth_id' in session and 'indieauth_token' in session:
        app.logger.info('session cookie found')
        indieauth_id    = session['indieauth_id']
        indieauth_token = session['indieauth_token']
        if db is not None:
            key = db.get('token-%s' % indieauth_token)
            if key:
                data = db.hgetall(key)
                if data and data['token'] == indieauth_token:
                    authed = True
    return authed, indieauth_id

def checkAccessToken(access_token):
    if db is not None:
        key = db.get('token-%s' % access_token)
        if key:
            data      = key.split('-')
            me        = data[1]
            client_id = data[2]
            scope     = data[3]
            return me, client_id, scope
    else:
        return None, None, None

@app.route('/logout', methods=['GET'])
def handleLogout():
    app.logger.info('handleLogout [%s]' % request.method)
    clearAuth()
    return redirect('/')

@app.route('/login', methods=['GET', 'POST'])
def handleLogin():
    app.logger.info('handleLogin [%s]' % request.method)

    me          = None
    redirectURI = '%s/success' % cfg.baseurl
    fromURI     = request.args.get('from_uri')
    # if fromURI is None:
    #     fromURI = '%s/login' % cfg.baseurl
    app.logger.info('redirectURI [%s] fromURI [%s]' % (redirectURI, fromURI))
    form = LoginForm(me='', 
                     client_id=cfg.client_id, 
                     redirect_uri=redirectURI, 
                     from_uri=fromURI)

    if form.validate_on_submit():
        app.logger.info('me [%s]' % form.me.data)

        me            = baseDomain(form.me.data)
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
                                                     'scope':         'post',
                                                     'response_type': 'id'
                                                   }),
                                  authURL.fragment).geturl()
                if db is not None:
                    key  = 'login-%s' % me
                    data = db.hgetall(key)
                    if data and 'token' in data: # clear any existing auth data
                        db.delete('token-%s' % data['token'])
                        db.hdel(key, 'token')
                    db.hset(key, 'from_uri',     form.from_uri.data)
                    db.hset(key, 'redirect_uri', form.redirect_uri.data)
                    db.hset(key, 'client_id',    form.client_id.data)
                    db.hset(key, 'scope',        'post')
                    db.expire(key, cfg['auth_timeout']) # expire in N minutes unless successful
                return redirect(url)
        else:
            return 'insert fancy no auth endpoint found error message here', 403

    buildTemplateContext(cfg, me)
    templateContext['title'] = 'Sign In'
    templateContext['form']  = form
    return render_template('login.jinja', **templateContext)

@app.route('/success', methods=['GET',])
def handleLoginSuccess():
    app.logger.info('handleLoginSuccess [%s]' % request.method)
    me   = request.args.get('me')
    code = request.args.get('code')
    app.logger.info('me [%s] code [%s]' % (me, code))

    if db is not None:
        app.logger.info('getting data to validate auth code')
        key  = 'login-%s' % me
        data = db.hgetall(key)
        if data:
            r = ninka.indieauth.validateAuthCode(code=code, 
                                                 client_id=me,
                                                 redirect_uri=data['redirect_uri'])
            if r['status'] == requests.codes.ok:
                app.logger.info('login code verified')
                scope    = r['response']['scope']
                from_uri = data['from_uri']
                token    = str(uuid.uuid4())

                db.hset(key, 'code',  code)
                db.hset(key, 'token', token)
                db.expire(key, cfg['auth_timeout'])
                db.set('token-%s' % token, key)
                db.expire('token-%s' % code, cfg['auth_timeout'])

                session['indieauth_token'] = token
                session['indieauth_scope'] = scope
                session['indieauth_id']    = me
            else:
                app.logger.info('login invalid')
                clearAuth()
        else:
            app.logger.info('nothing found for [%s]' % me)

    if scope:
        if from_uri:
            return redirect(from_uri)
        else:
            return redirect('/')
    else:
        return 'authentication failed', 403

@app.route('/auth', methods=['GET',])
def handleAuth():
    app.logger.info('handleAuth [%s]' % request.method)
    result = False
    if db is not None:
        token = request.args.get('token')
        if token is not None:
            me = db.get('token-%s' % token)
            if me:
                data = db.hgetall(me)
                if data and data['token'] == token:
                    result = True
    if result:
        return 'valid', 200
    else:
        clearAuth()
        return 'invalid', 403

@app.route('/micropub', methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'])
def handleMicroPub():
    app.logger.info('handleMicroPub [%s]' % request.method)
    # form = MicroPubForm()

    access_token = request.headers.get('Authorization')
    if access_token:
        access_token = access_token.replace('Bearer ', '')
    me, client_id, scope = checkAccessToken(access_token)

    app.logger.info('micropub %s [%s] [%s, %s, %s]' % (request.method, access_token, me, client_id, scope))
    app.logger.info(request.args)
    app.logger.info(request.form)

    if me is None or client_id is None:
        return ('Invalid access_token', 400, {})
    else:
        if request.method == 'POST':
                domain = baseDomain(me, includeScheme=False)
                if domain == 'bear.im':
                    data = { 'domain': domain }
                    for key in ('h', 'name', 'summary', 'content', 'published', 'updated', 'category', 
                                'slug', 'location', 'in-reply-to', 'repost-of', 'syndication', 'syndicate-to'):
                        data[key] = request.form.get(key)
                    events('micropub', 'setup', cfg, app.logger)
                    return events('micropub', 'process', data, getDomainConfig(domain))
                else:
                    return 'unauthorized', 401
        elif request.method == 'GET':
            # add support for /micropub?q=syndicate-to
            return 'not implemented', 501

@app.route('/token', methods=['POST', 'GET'])
def handleToken():
    app.logger.info('handleToken [%s]' % request.method)

    if request.method == 'GET':
        access_token = request.headers.get('Authorization')
        if access_token:
            access_token = access_token.replace('Bearer ', '')
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

        r = ninka.indieauth.validateAuthCode(code=code, 
                                             client_id=me,
                                             state=state,
                                             redirect_uri=redirect_uri)
        if r['status'] == requests.codes.ok:
            app.logger.info('token request auth code verified')
            scope = r['response']['scope']
            key   = 'app-%s-%s-%s' % (me, client_id, scope)
            token = db.get(key)
            if token is None:
                token     = str(uuid.uuid4())
                token_key = 'token-%s' % token
                db.set(key, token)
                db.set(token_key, key)

            app.logger.info('[%s] [%s]' % (key, token))

            params = { 'me': me,
                       'scope': scope,
                       'access_token': token
                     }
            return (urllib.urlencode(params), 200, {'Content-Type': 'application/x-www-form-urlencoded'})

# def validURL(targetURL):
#     """Validate the target URL exists by making a HEAD request for it
#     """
#     result = 404
#     try:
#         r = requests.head(targetURL)
#         result = r.status_code
#     except:
#         result = 404
#     return result

def mention(sourceURL, targetURL, vouchDomain=None):
    """Process the Webmention of the targetURL from the sourceURL.

    To verify that the sourceURL has indeed referenced our targetURL
    we run findMentions() at it and scan the resulting href list.
    """
    app.logger.info('discovering Webmention endpoint for %s' % sourceURL)

    mentions = ronkyuu.findMentions(sourceURL)
    result   = False
    app.logger.info('mentions %s' % mentions)
    for href in mentions['refs']:
        if href != sourceURL and href == targetURL:
            app.logger.info('post at %s was referenced by %s' % (targetURL, sourceURL))
            events('webmention', 'setup', cfg, app.logger)
            domain = baseDomain(targetURL, includeScheme=False)
            result = events('webmention', 'inbound', sourceURL, targetURL, vouchDomain, getDomainConfig(domain))
    app.logger.info('mention() returning %s' % result)
    return result

@app.route('/webmention', methods=['POST'])
def handleWebmention():
    app.logger.info('handleWebmention [%s]' % request.method)
    if request.method == 'POST':
        valid  = False
        source = request.form.get('source')
        target = request.form.get('target')
        vouch  = request.form.get('vouch')
        app.logger.info('source: %s target: %s vouch %s' % (source, target, vouch))

        if '/bearlog' in target:
            valid = validURL(target)

            app.logger.info('valid? %s' % valid)

            if valid == requests.codes.ok:
                if mention(source, target, vouch):
                    return redirect(target)
                else:
                    if vouch is None and cfg.require_vouch:
                        return 'Vouch required for webmention', 449
                    else:
                        return 'Webmention is invalid', 400
            else:
                return 'invalid post', 404
        else:
            return 'invalid post', 404

def initLogging(logger, logpath=None, echo=False):
    logFormatter = logging.Formatter("%(asctime)s %(levelname)-9s %(message)s", "%Y-%m-%d %H:%M:%S")

    if logpath is not None:
        from logging.handlers import RotatingFileHandler

        logfilename = os.path.join(logpath, 'indieweb.log')
        logHandler  = logging.handlers.RotatingFileHandler(logfilename, maxBytes=1024 * 1024 * 100, backupCount=7)
        logHandler.setFormatter(logFormatter)
        logger.addHandler(logHandler)

    if echo:
        echoHandler = logging.StreamHandler()
        echoHandler.setFormatter(logFormatter)
        logger.addHandler(echoHandler)

    logger.setLevel(logging.INFO)
    logger.info('starting kaku')

def loadConfig(configFilename, host=None, port=None, logpath=None):
    result = Config()
    result.fromJson(configFilename)

    if host is not None:
        result.host = host
    if port is not None:
        result.port = port
    if logpath is not None:
        result.paths.log = logpath
    if 'auth_timeout' not in result:
        result.auth_timeout = 300
    if 'require_vouch' not in result:
        result.require_vouch = False

    return result

def getRedis(config):
    if 'host' not in config:
        config.host = '127.0.0.1'
    if 'port' not in config:
        config.port = 6379
    if 'db' not in config:
        config.db = 0
    return redis.StrictRedis(host=config.host, port=config.port, db=config.db)

def doStart(app, configFile, ourHost=None, ourPort=None, ourBasePath=None, ourPath=None, echo=False):
    _cfg = loadConfig(configFile, host=ourHost, port=ourPort, basepath=ourBasePath, logpath=ourPath)
    _db  = None
    if 'secret' in _cfg:
        app.config['SECRET_KEY'] = _cfg.secret
    initLogging(app.logger, _cfg.paths.log, echo=echo)
    if 'redis' in _cfg:
        _db = getRedis(_cfg.redis)
    return _cfg, _db

if _uwsgi:
    cfg, db = doStart(app, _configFile, _ourPath)
    events  = Events(cfg.handlerspath)
#
# None of the below will be run for nginx + uwsgi
#
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--host',     default='0.0.0.0')
    parser.add_argument('--port',     default=5000, type=int)
    parser.add_argument('--logpath',  default='.')
    parser.add_argument('--basepath', default='/opt/kaku/')
    parser.add_argument('--config',   default='./kaku.cfg')

    args    = parser.parse_args()
    cfg, db = doStart(app, args.config, args.host, args.port, args.basepath, args.logpath, echo=True)
    events  = Events(cfg.handlerspath)

    app.run(host=cfg.host, port=cfg.port, debug=True)
