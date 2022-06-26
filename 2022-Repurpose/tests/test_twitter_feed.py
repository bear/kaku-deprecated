# -*- coding: utf-8 -*-
"""
:copyright: (c) 2016 by Mike Taylor
:license: CC0 1.0 Universal, see LICENSE for more details.
"""

import twitter_feed

class TestTwitterFeed:
    def test_domain(self):
        """Test validation of the domain
        """
        domains = [ (None, None),
                    ('bear.im', None),
                    ('https://bear.im',              'https://bear.im'),
                    ('https://bear.im/foo',          'https://bear.im/foo'),
                    ('https://bear.im/foo/',         'https://bear.im/foo/'),
                    ('https://bear.im?foo=bar',       'https://bear.im'),
                    ('https://bear.im/foo?foo=bar',  'https://bear.im/foo'),
                    ('https://bear.im/foo/?foo=bar', 'https://bear.im/foo/'),
                  ]
        for domain, expected in domains:
            assert twitter_feed.validateDomain(domain) == expected

    def test_token(self):
        """Test validation of the token
        """
        assert twitter_feed.validateToken() is None
        assert twitter_feed.validateToken('foobar') == 'foobar'
        assert twitter_feed.validateToken(None, './tests/token_test_file.txt') == 'foobar'
        assert twitter_feed.validateToken(None, './tests/bad_filename') is None
