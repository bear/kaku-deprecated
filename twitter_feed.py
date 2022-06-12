#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
:copyright: (c) 2013-2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""

import os
import sys
import logging
import argparse

try:
    # python 3
    from urllib.parse import ParseResult, urlparse
except ImportError:
    from urlparse import ParseResult, urlparse

from bearlib.tools import normalizeFilename
from bearlib.config import Config, findConfigFile


logger = logging.getLogger(__name__)

# key   = 'kaku-event::%s::%s::%s' % ('post', state, str(uuid.uuid4()))
# data  = { 'type':   'post',
#           'action': state,
#           'data':   { 'path': path,
#                       'file': filename
#                     },
#           'key':    key
#         }
# db.set(key, json.dumps(data))
# db.publish(cfg.events, key)

# Example config file
# {
#     "baseroute":  "/bearlog/",
#     "baseurl":    "https://bear.im",
#     "index_articles": 15,
#     "redis": "redis://127.0.0.1:6379/1",
#     "markdown_extras": [ "fenced-code-blocks", "cuddled-lists" ],
#     "logname": "kaku_events.log",
#     "events": "kaku-events",
#     "paths": {
#         "templates": "/home/bearim/templates/",
#         "content":   "/home/bearim/content/",
#         "output":    "/srv/bear.im/bearlog/",
#         "log":       "/home/bearim/"
#     },
#     "templates": {
#         "post":     "article.jinja",
#         "mention":  "mention.jinja",
#         "postPage": "article_page.jinja",
#         "index":    "blog_index.jinja",
#         "markdown": "post.md",
#         "embed":    "meta.embed"
#     }
# }


def validateDomain(domain=None):
    if domain is None:
        logger.error('A domain must be specified.')
        return None
    url = urlparse(domain)
    if len(url.scheme) == 0 or (url.netloc) == 0:
        logger.error('The domain must be specified with a scheme or location.')
        return None
    return ParseResult(url.scheme, url.netloc, url.path, '', '', '').geturl()

def validateToken(authToken=None, tokenFile=None):
    if authToken is None:
        if tokenFile is not None:
            tokenFile = normalizeFilename(tokenFile)
            if os.path.exists(tokenFile):
                with open(tokenFile, 'r') as h:
                    try:
                        authToken = h.read().strip()
                        if authToken is None or len(authToken) == 0:
                            logger.error('The authentication token found in %s appears to be empty.' % tokenFile)
                            authToken = None
                    except BaseException:
                        authToken = None
    if authToken is None:
        if tokenFile is not None:
            s = ' or retrieved at %s' % tokenFile
        else:
            s = ''
        logger.info('No Authorization token was found%s.' % s)
    return authToken

def main(cfg, domain=None, authToken=None, tokenFile=None):
    logger.info('twitter_feed started')

    domain    = validateDomain(domain)
    authToken = validateToken(authToken, tokenFile)

    if domain is None or authToken is None:
        return False
    else:
        print("do something")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='./kaku_events.cfg')
    parser.add_argument('--domain', default=None,
                        help='The domain to receive the micropub actions.')
    parser.add_argument('--tokenFile', default=None,
                        help='The file to retrieve the authentication token to use for micropub actions.')

    args     = parser.parse_args()
    cfgFiles = findConfigFile(args.config)
    cfg      = Config()

    if len(cfgFiles) > 0 and os.path.exists(cfgFiles[0]):
        cfg.fromJson(cfgFiles[0])

    logHandler   = logging.StreamHandler()
    logFormatter = logging.Formatter("%(asctime)s %(levelname)-9s %(message)s", "%Y-%m-%d %H:%M:%S")
    logHandler.setFormatter(logFormatter)
    logger.addHandler(logHandler)
    logger.setLevel(logging.DEBUG)

    domain    = args.domain
    tokenFile = args.tokenFile

    if domain is None and isinstance(cfg.baseurl, str):
        domain = cfg.baseurl
    if tokenFile is None and isinstance(cfg.tokenfile, str):
        tokenFile = cfg.tokenfile

    if not main(cfg, domain, tokenFile):
        sys.exit(2)
