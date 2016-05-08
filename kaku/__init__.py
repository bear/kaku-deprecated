# -*- coding: utf-8 -*-
"""
:copyright: (c) 2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""
import os
import jinja2
import logging
import logging.handlers

from flask import Flask
from flask.ext.redis import FlaskRedis
from redis import StrictRedis

from bearlib.config import Config

from kaku.controllers.main import main
from kaku.controllers.auth import auth
from kaku.extensions import (
    debug_toolbar,
    cache
)


def create_app(object_name):
    """
    An flask application factory, as explained here:
    http://flask.pocoo.org/docs/patterns/appfactories/

    Arguments:
        object_name: the python path of the config object,
                     e.g. appname.settings.ProdConfig
    """
    app = Flask(__name__)

    app.config.from_object(object_name)
    if os.environ.get('KAKU_SETTINGS', None) is not None:
        app.config.from_envvar('KAKU_SETTINGS')

    if not app.debug:
        handler   = logging.handlers.RotatingFileHandler(app.config['LOG_FILE'], maxBytes=100000000, backupCount=9)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(pathname)s:%(lineno)d -- %(message)s')
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)

        app.logger.addHandler(handler)
        app.logger.setLevel(logging.DEBUG)

        wzlog = logging.getLogger('werkzeug')
        wzlog.setLevel(logging.DEBUG)
        wzlog.addHandler(handler)

    if app.config['SITE_TEMPLATES'] is not None:
        app.jinja_loader = jinja2.FileSystemLoader(app.config['SITE_TEMPLATES'])

    # initialize the cache
    cache.init_app(app)

    # initialize the debug tool bar
    debug_toolbar.init_app(app)

    app.siteConfig = Config()
    app.siteConfig.fromJson(app.config['SITE_CONFIG'])

    app.dbRedis = FlaskRedis.from_custom_provider(StrictRedis, app)

    # register our blueprints
    app.register_blueprint(main)
    app.register_blueprint(auth)

    app.logger.info('Flask app [%s] created' % __name__)

    return app
