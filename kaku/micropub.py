# -*- coding: utf-8 -*-
"""
:copyright: (c) 2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""

import os
import re
import datetime

from unidecode import unidecode

import pytz

from flask import current_app

from kaku.tools import kakuEvent


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
def createSlug(title, delim=u'-'):
    result = []
    for word in _punct_re.split(title.lower()):
        result.extend(unidecode(word).split())
    return unicode(delim.join(result))

# TODO: figure out how to make determination of the title configurable
def determineTitle(mpData, timestamp):
    summary = ''
    if 'summary' in mpData and mpData['summary'] is not None:
        summary = mpData['summary']
    if len(summary) == 0:
        if 'content' in mpData and mpData['content'] is not None:
            summary = mpData['content'].split('\n')[0]
    if len(summary) == 0:
        title = 'micropub post %s' % timestamp.strftime('%H%M%S')
    else:
        title = summary
    return title

# TODO: figure out how to make the calculation of the location configurable
def generateLocation(timestamp, slug):
    baseroute = current_app.config['BASEROUTE']
    year      = str(timestamp.year)
    doy       = timestamp.strftime('%j')
    location  = os.path.join(baseroute, year, doy, slug)
    return location

def micropub(event, mpData):
    if event == 'POST':
        if 'h' in mpData:
            if mpData['h'].lower() not in ('entry',):
                return ('Micropub CREATE requires a valid action parameter', 400, {})
            else:
                try:
                    utcdate   = datetime.datetime.utcnow()
                    tzLocal   = pytz.timezone('America/New_York')
                    timestamp = tzLocal.localize(utcdate, is_dst=None)
                    title     = determineTitle(mpData, timestamp)
                    slug      = createSlug(title)
                    location  = generateLocation(timestamp, slug)
                    if os.path.exists(os.path.join(current_app.siteConfig.paths.content, '%s.md' % location)):
                        return ('Micropub CREATE failed, location already exists', 406)
                    else:
                        data = { 'slug':      slug,
                                 'title':     title,
                                 'location':  location,
                                 'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                                 'micropub':  mpData,
                               }
                        current_app.logger.info('micropub create event for [%s]' % slug)
                        kakuEvent('post', 'created', data)
                        return ('Micropub CREATE successful for %s' % location, 202, {'Location': location})
                except:
                    current_app.logger.exception('Exception during micropub handling')
                    return ('Unable to process Micropub', 400, {})
        else:
            return ('Invalid Micropub CREATE request', 400, {})
    else:
        return ('Unable to process Micropub %s' % data['event'], 400, {})
