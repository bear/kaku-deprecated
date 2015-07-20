# kaku
書く- to write

This is the code I have used to enable a IndieWeb Micropub endpoint for my static site.

This code is very opinionated as I am first writing it for my own use, but even with that warning I am still trying to keep things as configurable as possible.

## Requirements and Assumptions
- Python v2.7
- Kaku is written using Flask and takes advantage of the built Jinja templates.
- Because Kaku needs to handle within a stateless environment the authentication and authorization, it requires a redis database to work with locally.
- The messy storing and retrieving of webmentions is handled via my very (oh so very) simple "event handler" code that is within [bearlib](https://github.com/bear/bearlib)

## Installation
All of the dependencies are outlined in a pip installable '''requirements.txt''' file.

## Notes to myself
Testing locally

    python kaku.py --logpath . --port 9999 --host 127.0.0.1 --config ./kaku.cfg
