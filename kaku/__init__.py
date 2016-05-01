# -*- coding: utf-8 -*-
"""
:copyright: (c) 2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""
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

    # initialize the cache
    cache.init_app(app)

    # initialize the debug tool bar
    debug_toolbar.init_app(app)

    app.dbRedis = FlaskRedis.from_custom_provider(StrictRedis, app)

    app.siteConfig = Config()
    app.siteConfig.fromJson(app.config['SITE_CONFIG'])

    # register our blueprints
    app.register_blueprint(main)
    app.register_blueprint(auth)

    return app
