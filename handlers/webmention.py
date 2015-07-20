#!/usr/bin/env python

import os, sys
import datetime

from urlparse import urlparse, ParseResult
from mf2py.parser import Parser

import ronkyuu

cfg = None
log = None

def setup(config, logger):
    cfg = config
    log = logger


_mention = """date: %(postDate)s
url: %(sourceURL)s

[%(sourceURL)s](%(sourceURL)s)
"""

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
    mentionPath = os.path.join(cfg.contentpath, 'content', basePath)
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
    vouchDomains = []
    vouchFile    = os.path.join(cfg['basepath'], 'vouch_domains.txt')
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

def processWebmention(sourceURL, targetURL, vouchDomain=None):
    result = False
    with open(os.path.join(cfg['logpath'], 'mentions.log'), 'a+') as h:
        h.write('target=%s source=%s vouch=%s\n' % (targetURL, sourceURL, vouchDomain))

    r = requests.get(sourceURL, verify=False)
    if r.status_code == requests.codes.ok:
        mentionData = { 'sourceURL':   sourceURL,
                        'targetURL':   targetURL,
                        'vouchDomain': vouchDomain,
                        'vouched':     False,
                        'received':    datetime.date.today().strftime('%d %b %Y %H:%M'),
                        'postDate':    datetime.date.today().strftime('%Y-%m-%dT%H:%M:%S')
                      }
        if 'charset' in r.headers.get('content-type', ''):
            mentionData['content'] = r.text
        else:
            mentionData['content'] = r.content

        if vouchDomain is not None and cfg['require_vouch']:
            mentionData['vouched'] = processVouch(sourceURL, targetURL, vouchDomain)
            result                 = mentionData['vouched']
            log.info('result of vouch? %s' % result)
        else:
            result = not cfg['require_vouch']
            log.info('no vouch domain, result %s' % result)

        mf2Data = Parser(doc=mentionData['content']).to_dict()
        hcard   = extractHCard(mf2Data)

        mentionData['hcardName'] = hcard['name']
        mentionData['hcardURL']  = hcard['url']
        mentionData['mf2data']   = mf2Data

        sData  = json.dumps(mentionData)
        safeID = generateSafeName(sourceURL)
        if db is not None:
            db.set('mention::%s' % safeID, sData)

        targetFile = os.path.join(cfg.basepath, safeID)
        with open(targetFile, 'a+') as h:
            h.write(sData)

        mentionFile = generateMentionName(targetURL, result)
        with open(mentionFile, 'w') as h:
            h.write(_mention % mentionData)

    return result
