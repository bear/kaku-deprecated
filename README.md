[![Downloads](https://img.shields.io/pypi/v/kaku.svg)](https://pypi.python.org/pypi/kaku/)
[![Requirements Status](https://requires.io/github/bear/kaku/requirements.svg?branch=master)](https://requires.io/github/bear/kaku/requirements/?branch=master)

書く- to write

This is the code I have used to enable a IndieWeb Micropub endpoint for [my static site](https://bear.im/bearlog).

This code is very opinionated as I am first writing it for my own use, but even with that warning I am still trying to keep things as configurable as possible.

Currently Kaku implements:
- a Micropub endpoint ```/micropub``` that handles create evnts
- a Webmention endpoint ```/webmention```
- an Indieauth set of endpoints ```/login```, ```/logout```, ```/auth``` and ```/success```
- a Token generation endpoint ```/token```

As much as possible Kaku uses the configuration of the static site generator and it's templates, very little is hard-coded and I'm working on removing the remaining items that are.

## Configuration

Kaku uses a ```settings.py``` configuration file and includes a default one for reference at https://github.com/bear/kaku/blob/master/kaku/settings.py

## Requirements and Assumptions
- Python v2.7
- Kaku is written using Flask and takes advantage of the builtin Jinja templates
- Because Kaku needs to handle the occasional state information for authentication and authorization, it requires a Redis database to work with locally
- Flask is configured to take advantage of the Redis database for caching in production
- Kaku doesn't do anything with the Micropub or the Webmention calls, instead it publishes them Redis Pub/Sub to be processed later

## Installation
All of the dependencies are outlined in a pip installable '''requirements.txt''' file.

## Running

```
 KAKU_SETTINGS=/home/bearim/kaku_settings.py uwsgi --socket 127.0.0.1:5000 --module service --callable application
```

## TODO
handle the following requests:

- ```GET /.well-known/browserid?domain=palala.org```
- Micropub Edit and Delete events
