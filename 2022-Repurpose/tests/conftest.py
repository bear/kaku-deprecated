# -*- coding: utf-8 -*-
"""
:copyright: (c) 2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""

import pytest
from kaku import create_app


@pytest.yield_fixture
def app():
    app = create_app('kaku.settings.TestConfig')
    yield app

@pytest.yield_fixture
def app_client(app):
    client = app.test_client()
    yield client
