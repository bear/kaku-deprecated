#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
:copyright: (c) 2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""

from kaku import create_app

# ALWAYS start the service in production mode
#
# developer testing should be done using the
# 'server' Makefile target
application = create_app('kaku.settings.ProdConfig')

if __name__ == "__main__":
    application.run()
