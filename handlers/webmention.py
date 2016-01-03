#!/usr/bin/env python

import os
import json
import datetime

from urlparse import urlparse
from mf2py.parser import Parser
from bearlib.config import Config

import pytz
import ninka
import ronkyuu


siteConfig = Config()

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

def generateMentionName(targetURL, vouched):
    urlData     = urlparse(targetURL)
    urlPaths    = urlData.path.split('/')
    basePath    = '/'.join(urlPaths[2:-1])
    mentionPath = os.path.join(siteConfig.paths.content, 'content', basePath)
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

def processVouch(sourceURL, targetURL, vouchDomain):
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

def mention(sourceURL, targetURL, db, log, siteConfigFilename, vouchDomain=None, vouchRequired=False):
    """Process the Webmention of the targetURL from the sourceURL.

    To verify that the sourceURL has indeed referenced our targetURL
    we run findMentions() at it and scan the resulting href list.
    """
    # yes, I know, it's a module global...
    if os.path.exists(siteConfigFilename):
        siteConfig.fromJson(siteConfigFilename)
    siteConfig.db  = db
    siteConfig.log = log

    log.info('discovering Webmention endpoint for %s' % sourceURL)

    mentions = ronkyuu.findMentions(sourceURL)
    result   = False
    vouched  = False
    log.info('mentions %s' % mentions)
    with open(os.path.join(siteConfig.paths.content, 'mentions.log'), 'a+') as h:
        h.write('target=%s source=%s vouch=%s\n' % (targetURL, sourceURL, vouchDomain))
    for href in mentions['refs']:
        if href != sourceURL and href == targetURL:
            log.info('post at %s was referenced by %s' % (targetURL, sourceURL))
            utcdate   = datetime.datetime.utcnow()
            tzLocal   = pytz.timezone('America/New_York')
            timestamp = tzLocal.localize(utcdate, is_dst=None)

            if vouchRequired:
                if vouchDomain is None:
                    vouched = False
                    result  = False
                else:
                    vouched = processVouch(siteConfig.paths.content, sourceURL, targetURL, vouchDomain)
                    result  = vouched
            else:
                vouched = False
                result  = True

            if result:
                mf2Data = Parser(doc=mentions['content']).to_dict()
                hcard   = extractHCard(mf2Data)
                event   = { 'type':        'webmention',
                            'sourceURL':   sourceURL,
                            'targetURL':   targetURL,
                            'vouchDomain': vouchDomain,
                            'vouched':     vouched,
                            'received':    timestamp.strftime('%d %b %Y %H:%M'),
                            'postDate':    timestamp.strftime('%Y-%m-%dT%H:%M:%S'),
                            'payload':     {
                                'hcard': hcard,
                                'mf2data': mf2Data,
                            },
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

                if db is not None:
                    db.rpush('kaku-events', json.dumps(event))
                    result = True
                else:
                    result = False

    log.info('mention() returning %s' % result)
    return result, vouched
