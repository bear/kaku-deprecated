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

from flask import current_app
from mf2py.parser import Parser

from kaku.tools import kakuEvent, extractHCard


def processVouch(sourceURL, targetURL, vouchDomain):
    """Determine if the vouch domain is valid.

    This implements a very simple method for determining if a vouch should
    be considered valid:
      1. does the vouch domain have it's own webmention endpoint
      2. does the vouch domain have an indieauth endpoint
      3. does the domain exist in the list of domains i've linked to
    """
    result       = False
    vouchDomains = []
    vouchFile    = os.path.join(current_app.config['SITE_CONTENT'], 'vouch_domains.txt')
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
    """Process the incoming Webmention from the sourceURL.

    To verify that the targetURL being referenced by the sourceURL
    is a valid reference we run findMentions() at it and scan the
    resulting href list.

    This does the following checks:
      1. The sourceURL exists
      2. The sourceURL indeed does reference our targetURL
      3. The sourceURL is a valid Vouch (if configured to check)
      4. The sourceURL is active and not deleted, if deleted then remove
         it from our list of mentions for targetURL
    """
    current_app.logger.info('handling Webmention from %s' % sourceURL)

    try:
        result   = False
        vouched  = False
        mentions = ronkyuu.findMentions(sourceURL)
        current_app.logger.info('mentions %s' % mentions)

        if mentions['status'] == 410:
            data = { 'targetURL': targetURL,
                     'sourceURL': sourceURL
                   }
            current_app.logger.info('mention removal event from [%s] of [%s]' % (targetURL, sourceURL))
            kakuEvent('mention', 'deleted', data)
        else:
            for href in mentions['refs']:
                if href != sourceURL and href == targetURL:
                    current_app.logger.info('post at %s was referenced by %s' % (targetURL, sourceURL))
                    if current_app.config['VOUCH_REQUIRED']:
                        if vouchDomain is None:
                            vouched = False
                            result  = False
                        else:
                            vouched = processVouch(sourceURL, targetURL, vouchDomain)
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
                        current_app.logger.info('mention created for [%s] from [%s]' % (targetURL, sourceURL))
                        current_app.logger.info(json.dumps(data, indent=2))
                        kakuEvent('mention', 'create', data)

        current_app.logger.info('mention() returning %s' % result)
    except ValueError:
        current_app.logger.exception('Exception raised during webmention processing')
        result = False
    return result, vouched
