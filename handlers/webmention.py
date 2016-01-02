#!/usr/bin/env python

import os, sys
import datetime

from urlparse import urlparse, ParseResult
from mf2py.parser import Parser
from bearlib.config import Config

import ronkyuu


_ourPath = os.path.dirname(__file__)

def setup(config, logger):
    pass

_mention = """date: %(postDate)s
url: %(sourceURL)s

[%(sourceURL)s](%(sourceURL)s)
"""

#
# this handler expects a config file to be found in the same directory
# where it is located that points to the domain's configuration
# e.g. ./<domain>.cfg
#
def getDomainConfig(domain=None):
    result  = None
    cfgfile = os.path.join(_ourPath, '%s.cfg' % domain)
    if domain is not None and os.path.exists(cfgfile):
        result = Config()
        result.fromJson(cfgfile)
    return result

def buildTemplateContext(config, domainCfg):
    result = {}
    for key in ('baseurl', 'title', 'meta'):
        if key in domainCfg:
            value = domainCfg[key]
        else:
            value = ''
        result[key] = value
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

def inbound(domain, sourceURL, targetURL, vouchDomain=None, db=None):
    result = False
    with open(os.path.join(_ourPath, 'mentions.log'), 'a+') as h:
        h.write('target=%s source=%s vouch=%s\n' % (targetURL, sourceURL, vouchDomain))

    domainCfg = getDomainConfig(domain)
    if domainCfg is not None:
        mentionData = { 'sourceURL':   sourceURL,
                        'targetURL':   targetURL,
                        'vouchDomain': vouchDomain,
                        'vouched':     False,
                        'received':    datetime.date.today().strftime('%d %b %Y %H:%M'),
                        'postDate':    datetime.date.today().strftime('%Y-%m-%dT%H:%M:%S')
                      }
        if vouchDomain is not None and domainCfg.require_vouch:
            mentionData['vouched'] = processVouch(sourceURL, targetURL, vouchDomain)
            result                 = mentionData['vouched']
            log.info('result of vouch? %s' % result)
        else:
            result = True

        if result:
            # mf2Data = Parser(doc=mentionData['content']).to_dict()
            # hcard   = extractHCard(mf2Data)

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
               db.rpush('webmentions', json.dumps(mentionData))

    return result
