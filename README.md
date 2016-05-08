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

## Gathering

Included is a small tool I call ```gather``` which, as you would imagine, is used to gather up any changed markdown files found in the content path.

```
$ python gather.py --help
usage: gather.py [-h] [--redis REDIS] [--logpath LOGPATH] [--file FILE]
                 [--path PATH] [--force] [--listen]

optional arguments:
  -h, --help         show this help message and exit
  --redis REDIS      The Redis database to connect to as a URL.
                     Default is redis://127.0.0.1:6379/0
  --logpath LOGPATH  Where to write the log file output. Default is "."
  --file FILE        A specific markdown file to check and then exit.
  --path PATH        A path to scan for changed files.
  --force            Force any found markdown files (or specific file) to be
                     considered an update.
  --listen           Listen for publish events from Redis.
```

Each file that is determined to be new, updated or deleted will have a Kaku Event generated -- which is fancy talk for it building a json blob and calling Redis ```publish``` on the ```kaku-event``` channel.

## TODO
handle the following requests:

- ```GET /.well-known/browserid?domain=palala.org```
- Micropub Edit and Delete events
