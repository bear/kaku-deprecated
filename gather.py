#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
:copyright: (c) 2013-2016 by Mike Taylor
:license: MIT, see LICENSE for more details.
"""

import os
import uuid
import json
import logging
import argparse

import redis

from urlparse import urlparse
from logging.handlers import RotatingFileHandler
from bearlib.tools import normalizeFilename


logger = logging.getLogger('gather')

def isUpdated(path, filename, force=False):
    mFile = os.path.join(path, '%s.md' % filename)
    jFile = os.path.join(path, '%s.json' % filename)
    if os.path.exists(os.path.join(path, '%s.deleted' % filename)):
        return 'deleted'
    if os.path.exists(jFile):
        mTime = os.path.getmtime(mFile)
        jTime = os.path.getmtime(jFile)
        if force or mTime > jTime:
            return 'updated'
        else:
            return 'unchanged'
    else:
        return 'created'

def gather(filepath, filename=None, force=False):
    logger.info('gather [%s] [%s] [%s]' % (filepath, filename, force))
    if filename is None:
        if filepath is None:
            logger.error('A specific file or a path to walk must be specified')
        else:
            for path, dirlist, filelist in os.walk(filepath):
                if len(filelist) > 0:
                    for item in filelist:
                        filename, ext = os.path.splitext(item)
                        if ext in ('.md',):
                            state = isUpdated(path, filename, force)
                            key   = 'kaku-event::%s::%s::%s' % ('post', state, str(uuid.uuid4()))
                            data  = { 'type':   'post',
                                      'action': state,
                                      'data':   { 'gatheredPath': path,
                                                  'gatheredFile': filename
                                                },
                                      'key':    key
                                    }
                            db.set(key, json.dumps(data))
                            db.publish('kaku', key)
    else:
        s = normalizeFilename(filename)
        if not os.path.exists(s):
            s = normalizeFilename(os.path.join(filepath, filename))
        logger.info('checking [%s]' % s)
        if os.path.exists(s):
            path          = os.path.dirname(s)
            filename, ext = os.path.splitext(s)
            if ext in ('.md',):
                state = isUpdated(path, filename, force)
                key   = 'kaku-event::%s::%s::%s' % ('post', state, str(uuid.uuid4()))
                data  = { 'type':   'post',
                          'action': state,
                          'data':   { 'gatheredPath': path,
                                      'gatheredFile': filename
                                    },
                          'key':    key
                        }
                db.set(key, json.dumps(data))
                db.publish('kaku', key)

def initLogging(logpath=None):
    logFormatter = logging.Formatter("%(asctime)s %(levelname)-9s %(message)s", "%Y-%m-%d %H:%M:%S")
    logfilename  = os.path.join(logpath, 'gather.log')
    logHandler   = RotatingFileHandler(logfilename, maxBytes=1024 * 1024 * 100, backupCount=7)
    logHandler.setFormatter(logFormatter)
    logger.addHandler(logHandler)
    logger.setLevel(logging.DEBUG)

def getRedis(redisURL):
    url  = urlparse(redisURL)
    host = url.netloc
    if ':' in host:
        host, port = host.split(':')
        port       = int(port)
    else:
        port = 6379
    if len(url.path) > 0:
        db = int(url.path[1:])
    else:
        db = 0
    return redis.StrictRedis(host=host, port=port, db=db)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--redis',   default='redis://127.0.0.1:6379/0',
                        help='The Redis database to connect to as a URL. Default is redis://127.0.0.1:6379/0')
    parser.add_argument('--logpath', default='.',
                        help='Where to write the log file output. Default is "."')
    parser.add_argument('--file',    default=None,
                        help='A specific markdown file to check and then exit.')
    parser.add_argument('--path',    default=None,
                        help='A path to scan for changed files.')
    parser.add_argument('--force',   default=False, action='store_true',
                        help='Force any found markdown files (or specific file) to be considered an update.')
    parser.add_argument('--listen',  default=False, action='store_true',
                        help='Listen for publish events from Redis.')
    args = parser.parse_args()

    initLogging(args.logpath)
    logger.info('starting gather')

    db = getRedis(args.redis)
    if args.listen:
        p = db.pubsub()
        p.subscribe('kaku')
        logger.info('listening for events')
        for item in p.listen():
            logger.info('event: [%s]' % json.dumps(item))
            if item['data'] == 'gather':
                gather(args.path)
    else:
        gather(args.path, args.file, args.force)
