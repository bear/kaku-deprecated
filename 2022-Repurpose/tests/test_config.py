# -*- coding: utf-8 -*-
"""
:copyright: (c) 2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""

from kaku import create_app

class TestConfig:
    def test_dev_config(self):
        """Test if the development config loads correctly
        """
        app = create_app('kaku.settings.DevConfig')

        assert app.config['DEBUG'] is True
        assert app.config['REDIS_URL']  == "redis://127.0.0.1:6379/0"
        assert app.config['CACHE_TYPE'] == 'null'

    def test_test_config(self):
        """Test if the test config loads correctly
        """
        app = create_app('kaku.settings.TestConfig')

        assert app.config['DEBUG'] is True
        assert app.config['REDIS_URL']  == "redis://127.0.0.1:6379/0"
        assert app.config['CACHE_TYPE'] == 'null'
