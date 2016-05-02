# -*- coding: utf-8 -*-
"""
:copyright: (c) 2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""

import os
import json
import datetime

import pytz
import ninka
import ronkyuu
import requests

from flask import Blueprint, current_app, redirect, request
from mf2py.parser import Parser

from kaku.tools import validURL, extractHCard


wm = Blueprint('wm', __name__)

def processVouch(sourceURL, targetURL, siteConfig, vouchDomain):
    """Determine if a vouch domain is valid.

    This implements a very simple method for determining if a vouch should
    be considered valid:
    1. does the vouch domain have it's own webmention endpoint
    2. does the vouch domain have an indieauth endpoint
    3. does the domain exist in the list of domains i've linked to

    yep, super simple but enough for me to test implement vouches
    """
    result       = False
    vouchDomains = []
    vouchFile    = os.path.join(siteConfig.paths.content, 'vouch_domains.txt')
    if os.isfile(vouchFile):
        with open(vouchFile, 'r') as h:
            for domain in h.readlines():
                vouchDomains.append(domain.strip().lower())

    # result = ronkyuu.vouch(sourceURL, targetURL, vouchDomain, vouchDomains)

    if vouchDomain.lower() in vouchDomains:
        result = True
    else:
        wmStatus, wmUrl = ronkyuu.discoverEndpoint(vouchDomain, test_urls=False)
        if wmUrl is not None and wmStatus == 200:
            authEndpoints = ninka.indieauth.discoverAuthEndpoints(vouchDomain)

            if 'authorization_endpoint' in authEndpoints:
                authURL = None
                for url in authEndpoints['authorization_endpoint']:
                    authURL = url
                    break
                if authURL is not None:
                    result = True
                    with open(vouchFile, 'a+') as h:
                        h.write('\n%s' % vouchDomain)
    return result

def mention(sourceURL, targetURL, vouchDomain=None):
    """Process the Webmention of the targetURL from the sourceURL.

    To verify that the sourceURL has indeed referenced our targetURL
    we run findMentions() at it and scan the resulting href list.
    """
    current_app.logger.info('handling Webmention from %s' % sourceURL)

    mentions = ronkyuu.findMentions(sourceURL)
    result   = False
    vouched  = False
    current_app.logger.info('mentions %s' % mentions)

    if mentions['status'] == 410:
        key       = 'mention::%s::%s' % (targetURL, sourceURL)
        event     = { 'type':    'mention',
                      'key':     key,
                      'action': 'deleted'
                    }
        current_app.logger.info('mention removal event for [%s]' % key)
        current_app.dbRedis.delete(key)
        current_app.dbRedis.rpush('kaku-events', json.dumps(event))
        current_app.dbRedis.publish('kaku', 'generate')
    else:
        for href in mentions['refs']:
            if href != sourceURL and href == targetURL:
                current_app.logger.info('post at %s was referenced by %s' % (targetURL, sourceURL))
                if current_app.config['VOUCH_REQUIRED']:
                    if vouchDomain is None:
                        vouched = False
                        result  = False
                    else:
                        vouched = processVouch(current_app.siteConfig.paths.content, sourceURL, targetURL, vouchDomain)
                        result  = vouched
                else:
                    vouched = False
                    result  = True

                if result:
                    utcdate   = datetime.datetime.utcnow()
                    tzLocal   = pytz.timezone('America/New_York')
                    timestamp = tzLocal.localize(utcdate, is_dst=None)
                    mf2Data   = Parser(doc=mentions['content']).to_dict()
                    hcard     = extractHCard(mf2Data)
                    data      = { 'sourceURL':   sourceURL,
                                  'targetURL':   targetURL,
                                  'vouchDomain': vouchDomain,
                                  'vouched':     vouched,
                                  'postDate':    timestamp.strftime('%Y-%m-%dT%H:%M:%S'),
                                  'hcard':       hcard,
                                  'mf2data':     mf2Data,
                                }
                    key       = 'mention::%s::%s' % (targetURL, sourceURL)
                    event     = { 'type':   'mention',
                                  'key':    key,
                                  'action': 'created'
                                }

                    # mentionData['hcardName'] = hcard['name']
                    # mentionData['hcardURL']  = hcard['url']
                    # mentionData['mf2data']   = mf2Data
                    # sData  = json.dumps(mentionData)
                    # safeID = generateSafeName(sourceURL)
                    # if db is not None:
                    #     db.set('mention::%s' % safeID, sData)

                    # targetFile = os.path.join(domainCfg.basepath, safeID)
                    # with open(targetFile, 'a+') as h:
                    #     h.write(sData)

                    # mentionFile = generateMentionName(targetURL, result)
                    # with open(mentionFile, 'w') as h:
                    #     h.write(_mention % mentionData)
                    current_app.logger.info('mention create event for [%s]' % key)
                    current_app.logger.info('\n\t'.join(json.dumps(data, indent=2)))

                    current_app.dbRedis.set(key, json.dumps(data))
                    current_app.dbRedis.rpush('kaku-events', json.dumps(event))
                    current_app.dbRedis.publish('kaku', 'generate')

    current_app.logger.info('mention() returning %s' % result)
    return result, vouched

@wm.route('/webmention', methods=['POST'])
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
