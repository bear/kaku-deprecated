#!/usr/bin/env python

import os, sys
import re
import datetime
import traceback

import pytz
from bearlib.config import Config
from bearlib.tools import normalizeFilename
from unidecode import unidecode


_ourPath = os.path.dirname(__file__)

def setup():
    pass

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

# from http://flask.pocoo.org/snippets/5/
_punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')
def createSlug(text, delim=u'-'):
    result = []
    for word in _punct_re.split(text.lower()):
        result.extend(unidecode(word).split())
    return unicode(delim.join(result))

def createPath(path):
    result = True
    try:
        print path
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        print exc
        if os.path.isdir(path):
            pass
        else:
            result = False
    print result
    return result

_article_file = """Title:   %(title)s
Date:    %(published)s
Tags:    %(tags)s
Author:  %(author)s
Slug:    %(slug)s
Summary: %(title)s

%(content)s
"""

def createBookmark(data, domainCfg, db):
    if 'published' in data and data['published'] is not None:
        d = parse(data['published'])
    else:
        d = datetime.datetime.utcnow()
    tzLocal   = pytz.timezone('America/New_York')
    timestamp = tzLocal.localize(d, is_dst=None)
    slug      = 'bookmarks'
    location  = os.path.join(domainCfg.contentpath, str(timestamp.year), timestamp.strftime('%j'), slug)
    task      = { 'action':    'create',
                  'type':      'bookmark',
                  'slug':      slug,
                  'url':       data['like-of']
                  'category':  data['category'],
                  'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                  'location':  location
                }
    if db is not None:
        db.rpush('micropub-tasks', json.dumps(task))
        code = 202
    else:
        code = 500
    return location, code

def createArticle(data, domainCfg, db):
    if 'published' in data and data['published'] is not None:
        d = parse(data['published'])
    else:
        d = datetime.datetime.utcnow()
    tzLocal   = pytz.timezone('America/New_York')
    timestamp = tzLocal.localize(d, is_dst=None)
    slug      = createSlug(title)
    location  = os.path.join(domainCfg.contentpath, str(timestamp.year), timestamp.strftime('%j'), slug)
    task      = { 'action':    'create',
                  'type':      'article',
                  'slug':      slug,
                  'title':     data['content'].split('\n')[0],
                  'content':   data['content'],
                  'category':  data['category'],
                  'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                  'location':  location
                }
    if db is not None:
        db.rpush('micropub-tasks', json.dumps(task))
        code = 202
    else:
        code = 500
    return location, code

def createNote(data, domainCfg, db):
    if 'published' in data and data['published'] is not None:
        d = parse(data['published'])
    else:
        d = datetime.datetime.utcnow()
    tzLocal   = pytz.timezone('America/New_York')
    timestamp = tzLocal.localize(d, is_dst=None)
    slug      = createSlug(title)
    location  = os.path.join(domainCfg.contentpath, str(timestamp.year), timestamp.strftime('%j'), slug)
    task      = { 'action':   'create',
                  'type':     'note',
                  'slug':     slug,
                  'title':    data['content'].split('\n')[0],
                  'content':  data['content'],
                  'category': data['category'],
                  'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                  'location':  location
                }
    if db is not None:
        db.rpush('micropub-tasks', json.dumps(task))
        code = 202
    else:
        code = 500
    return location, code

def process(data, db):
    try:
        if method == 'POST':
            if 'h' in data:
                action = data['h'].lower()

                if action not in ('entry',):
                    return ('Micropub CREATE requires a valid action parameter', 400, {})
                else:
                    location = None
                    code     = 400
                    if action == 'entry':
                        domainCfg = getDomainConfig(data['domain'])
                        if domainCfg is not None:
                            if 'like-of' in data:
                                location, code = createBookmark(data, domainCfg, db)
                            elif 'title' in data and data['title'] is not None:
                                location, code = createArticle(data, domainCfg, db)
                            else:
                                location, code = createNote(data, domainCfg, db)

                    if code in (202,):
                        return ('Micropub CREATE %s successful for %s' % (action, location), code, {'Location': location})
                    else:
                        return ('Micropub CREATE %s failed for %s' % (action, location), code, {})
            else:
                return ('Micropub CREATE requires an action parameter', 400, {})
        else:
            return ('Unable to process Micropub %s' % method, 400, {})
    except:
        pass
    
    # should only get here if an exception has occurred
    traceback.print_exc()
    return ('Unable to process Micropub %s' % method, 400, {})
