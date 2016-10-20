# -*- coding: utf-8 -*-
"""
:copyright: (c) 2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""

import os
import re
import datetime

from unidecode import unidecode
from urlparse import urlparse

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
def determineSummary(mpData, timestamp):
    summary   = ''
    mpSummary = mpData['summary']
    if len(mpSummary) > 0 and mpSummary[0] is not None:
        summary = ' '.join(mpData['summary'])
    current_app.logger.info('%d [%s]' % (len(summary), summary))
    if len(summary) == 0:
        if 'content' in mpData and mpData['content'] is not None and len(mpData['content']) > 1:
            summary = mpData['content'][0]
            if len(summary) > 0:
                mpData['content'] = mpData['content'][1:]
            current_app.logger.info('summary: %s' % summary)
            current_app.logger.info('mpData[content]: %s' % mpData['content'])
    if len(summary) == 0:
        summary = 'micropub post %s' % timestamp.strftime('%H%M%S')
    current_app.logger.info('summary: %s' % summary)
    return summary

# TODO: figure out how to make the calculation of the location configurable
def generateLocation(timestamp, slug):
    baseroute = current_app.config['BASEROUTE']
    year      = str(timestamp.year)
    doy       = timestamp.strftime('%j')
    location  = os.path.join(baseroute, year, doy, slug)
    return location

def micropub(event, mpData):
    if event == 'POST':
        properties = mpData['properties']

        if 'action' in properties:
            action = properties['action'].lower()
        elif 'mp-action' in properties and properties['mp-action'] is not None:
            action = properties['mp-action'].lower()
        else:
            action = None
        if action == 'create':
            if 'type' in properties and properties['type'] is not None:
                if properties['type'][0].lower() not in ('entry', 'h-entry'):
                    return ('Micropub CREATE requires a valid type parameter', 400, {})
            if 'content' not in properties and 'summary' in properties:
                properties['content'] = [ '\n'.join(properties['summary']) ]
                properties['summary'] = []
            if 'content' in properties or 'html' in properties:
                try:
                    utcdate    = datetime.datetime.utcnow()
                    tzLocal    = pytz.timezone('America/New_York')
                    timestamp  = tzLocal.localize(utcdate, is_dst=None)
                    title      = determineSummary(properties, timestamp)
                    slug       = createSlug(title)
                    location   = generateLocation(timestamp, slug)
                    targetFile = os.path.join(current_app.config['SITE_CONTENT'], '%s.md' % location)
                    if os.path.exists(targetFile):
                        return ('Micropub CREATE failed, location already exists', 406)
                    else:
                        data = { 'slug':      slug,
                                 'title':     title,
                                 'location':  location,
                                 'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                                 'micropub':  properties,
                               }
                        for key in data:
                            current_app.logger.info('    %s = %s' % (key, data[key]))
                        current_app.logger.info('micropub create event for [%s]' % slug)
                        kakuEvent('post', 'create', data)
                        return ('Micropub CREATE successful for %s' % location, 202, {'Location': location})
                except:
                    current_app.logger.exception('Exception during micropub handling')
                    return ('Unable to process Micropub request', 400, {})
            else:
                return ('Micropub CREATE requires a content or html property', 400, {})
        elif action == 'update':
            if 'url' not in properties:
                return ('Micropub UPDATE requires a url property', 400, {})
            location   = properties['url'].strip()
            targetPath = urlparse(location).path
            pathItems  = targetPath.split('.')
            current_app.logger.info('[%s] %s' % (targetPath, pathItems))
            if pathItems[-1].lower() == 'html':
                targetPath = '.'.join(pathItems[:-1])
            slug       = targetPath.replace(current_app.config['BASEROUTE'], '')
            targetFile = '%s.json' % os.path.join(current_app.config['SITE_CONTENT'], slug)

            if not os.path.exists(targetFile):
                return ('Micropub UPDATE failed for %s - location does not exist' % location, 404, {})
            else:
                for key in ('add', 'delete', 'replace'):
                    if key in properties:
                        if type(properties[key]) is list:
                            try:
                                data = { 'slug':      slug,
                                         'url':       location,
                                         'micropub':  properties[key],
                                         'actionkey': key
                                       }
                                current_app.logger.info('micropub UPDATE (%s) event for [%s]' % (key, slug))
                                kakuEvent('post', 'update', data)
                                return ('Micropub UPDATE successful for %s' % location, 200, {'Location': location})
                            except:
                                current_app.logger.exception('Exception during micropub handling')
                                return ('Unable to process Micropub request', 400, {})
                        else:
                            return ('Unable to process Micropub request', 400, {})
                else:
                    return ('Micropub UPDATE failed for %s - currently only REPLACE is supported' % location, 406, {})

        elif action in ('delete', 'undelete'):
            if 'url' in properties and properties['url'] is not None:
                url = properties['url']
                try:
                    data = { 'url': url }
                    kakuEvent('post', action, data)
                    return ('Micropub %s successful for %s' % (action, url), 200, {'Location': url})
                except:
                    current_app.logger.exception('Exception during micropub handling')
                    return ('Unable to process Micropub request', 400, {})
            else:
                return ('Micropub %s request requires a URL' % action, 400, {})
        else:
            return ('Invalid Micropub CREATE request', 400, {})
    else:
        return ('Unable to process Micropub %s' % data['event'], 400, {})
