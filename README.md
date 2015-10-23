# kaku
書く- to write

This is the code I have used to enable a IndieWeb Micropub endpoint for my static site.

This code is very opinionated as I am first writing it for my own use, but even with that warning I am still trying to keep things as configurable as possible.

Currently Kaku implements:
- Micropub Create events
- Inbound Webmention events
- Indieauth Login
- Token Endpoint

## Requirements and Assumptions
- Python v2.7,
- Kaku is written using Flask and takes advantage of the built Jinja templates,
- Because Kaku needs to handle within a stateless environment the authentication and authorization, it requires a Redis database to work with locally,
- Kaku doesn't do anything with the Micropub or the Webmention calls, instead it stores them into a Redis list that is then processed by another daemon

## Installation
All of the dependencies are outlined in a pip installable '''requirements.txt''' file.

## TODO
handle the following requests:

- ```GET /.well-known/browserid?domain=palala.org```
- Micropub Edit and Delete events

## Notes to myself
Testing locally

    python kaku.py --logpath . --port 9999 --host 127.0.0.1 --config ./kaku.cfg
