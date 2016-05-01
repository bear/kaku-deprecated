# -*- coding: utf-8 -*-
"""
:copyright: (c) 2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""

import os
import re
import json
import datetime
import traceback

from unidecode import unidecode

import pytz

from flask import current_app


def buildTemplateContext(cfg):
    result = {}
    for key in ('baseurl', 'title', 'meta'):
        if key in cfg:
            value = cfg[key]
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

def micropub(data):
    # yes, I know, it's a module global...
    try:
        if data['event'] == 'create':
            if 'h' in data:
                if data['h'].lower() not in ('entry',):
                    return ('Micropub CREATE requires a valid action parameter', 400, {})
                else:
                    try:
                        utcdate   = datetime.datetime.utcnow()
                        tzLocal   = pytz.timezone('America/New_York')
                        timestamp = tzLocal.localize(utcdate, is_dst=None)

                        if 'content' in data and data['content'] is not None:
                            title = data['content'].split('\n')[0]
                        else:
                            title = 'event-%s' % timestamp.strftime('%H%M%S')
                        slug     = createSlug(title)
                        year     = str(timestamp.year)
                        doy      = timestamp.strftime('%j')
                        location = os.path.join(data['baseroute'], year, doy, slug)

                        filename = os.path.join(current_app.siteConfig.paths.content, year, doy, '%s.md' % slug)
                        if os.path.exists(filename):
                          return ('Micropub CREATE failed, location already exists', 406)
                        else:
                          mdata = { 'slug':       slug,
                                    'timestamp':  timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                                    'location':   '%s%s' % (data['baseurl'], location),
                                    'year':       year,
                                    'doy':        doy,
                                    'micropub':   data,
                                  }
                          key   = 'micropub::%s::%s' % (timestamp.strftime('%Y%m%d%H%M%S'), slug)
                          event = { 'type': 'micropub',
                                    'key':  key,
                                  }
                          current_app.dbRedis.set(key, json.dumps(mdata))
                          current_app.dbRedis.rpush('kaku-events', json.dumps(event))
                          current_app.dbRedis.publish('kaku', 'update')
                          return ('Micropub CREATE successful for %s' % location, 202, {'Location': location})
                    except Exception:
                        current_app.log.exception('Exception during micropub handling')

                    return ('Micropub CREATE failed', 500, {})
            else:
                return ('Invalid Micropub CREATE request', 400, {})
        else:
            return ('Unable to process Micropub %s' % data['event'], 400, {})
    except:
        pass

    # should only get here if an exception has occurred
    traceback.print_exc()
    return ('Unable to process Micropub', 400, {})
