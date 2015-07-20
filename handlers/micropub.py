#!/usr/bin/env python

import os, sys
import re

import pytz


cfg = None
log = None

def setup(config, logger):
    cfg = config
    log = logger


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
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if os.path.isdir(path):
            pass
        else:
            result = False
    return result

_article_file = """Title:   %(title)s
Date:    %(published)s
Tags:    %(tags)s
Author:  %(author)s
Slug:    %(slug)s
Summary: %(title)s

%(content)s
"""

def createArticle(data, domainConfig):
    if 'published' in data and data['published'] is not None:
        d = parse(data['published'])
    else:
        d = datetime.datetime.utcnow()
    tzLocal   = pytz.timezone('America/New_York')
    published = tzLocal.localize(d, is_dst=None)
    app.logger.info('%s %s' % (d, published))

    code     = 400
    year     = str(published.year)
    doy      = published.strftime('%j')
    title    = data['title']
    slug     = createSlug(title)
    location = os.path.join(domainConfig.baseurl, domainConfig.contentroute, year, doy, slug)
    basepath = os.path.join(domainConfig.contentpath, 'content', year, doy)
    task     = { 'action':'create',
                 'type':  'article',
                 'data':  { 'title':     title,
                            'slug':      slug,
                            'content':   data['content'],
                            'tags':      ['mutterings'],
                            'author':    'bear',
                            'published': published.strftime('%Y-%m-%d %H:%M:%S'),
                            'year':      year,
                            'doy':       doy,
                            'basepath':  basepath,
                            'location':  location
                          }
               }
    target = os.path.join(basepath, '%s.md' % slug)
    if os.path.exists(target):
        code = 409
    else:
        if createPath(basepath):
            code = 202
            with open(target, 'w+') as h:
                h.write(_article_file % task['data'])
            # if db is not None:
            #     db.rpush('micropub-tasks', json.dumps(task))

    return location, code

noteTemplate = """<span id="%(url)s"><p class="byline h-entry" role="note"> <a href="%(url)s">%(name)s</a> <time datetime="%(date)s">%(date)s</time></p></span>
%(marker)s
"""

def createNote(data, domainConfig):
    if 'published' in data and data['published'] is not None:
        d = parse(data['published'])
    else:
        d = datetime.datetime.utcnow()
    tzLocal   = pytz.timezone('America/New_York')
    published = tzLocal.localize(d, is_dst=None)
    app.logger.info('%s %s' % (d, published))

    code     = 400
    year     = str(published.year)
    doy      = published.strftime('%j')
    title    = data['content'].split('\n')[0]
    slug     = createSlug(title)
    location = os.path.join(domainConfig.baseurl, domainConfig.contentroute, year, doy, slug)
    basepath = os.path.join(domainConfig.contentpath, 'content', year, doy)
    task     = { 'action':'create',
                 'type':  'article',
                 'data':  { 'title':     title,
                            'slug':      slug,
                            'content':   data['content'],
                            'tags':      ['mutterings'],
                            'author':    'bear',
                            'published': published.strftime('%Y-%m-%d %H:%M:%S'),
                            'year':      year,
                            'doy':       doy,
                            'basepath':  basepath,
                            'location':  location
                          }
               }
    target = os.path.join(basepath, '%s.md' % slug)
    if os.path.exists(target):
        code = 409
    else:
        if createPath(basepath):
            code = 202
            with open(target, 'w+') as h:
                h.write(_article_file % task['data'])
            # if db is not None:
            #     db.rpush('micropub-tasks', json.dumps(task))

    return location, code

def process(data, domainConfig):
    if request.method == 'POST':
        if 'h' in data:
            action = data['h'].lower()

            if action not in ('entry',):
                return ('Micropub CREATE requires a valid action parameter', 400, [])
            else:
                location = None
                code     = 400
                if action == 'entry':
                    if 'title' in data and data['title'] is not None:
                        location, code = createArticle(data, domainConfig)
                    else:
                        location, code = createNote(data, domainConfig)

                if code in (202,):
                    return ('Micropub CREATE %s successful for %s' % (action, location), code, {'Location': location})
                else:
                    return ('Micropub CREATE %s failed for %s' % (action, location), code, {})
        else:
            return ('Micropub CREATE requires an action parameter', 400, [])
    else:
        return ('Unable to process Micropub %s' % request.method, 400, [])
