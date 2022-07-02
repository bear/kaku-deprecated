# 書く kaku
to write 

Kaku by choice does NOT push, distribute or other post-process the generated files. This is to keep the core code specific to discovery and generation, publishing will most likely be handled by Hakkan.

## Discovery
Discovery of the items to generate is declarative and very purposeful, if a directory or file is not specified then it is ignored, this will both simplify the code for discovery and also allow for secondary metadata files to be added in future enhancements without requiring tweaks to kaku for special handling.

To enable this, and also to hopefully make the discovery code simple, the discovery part of kaku will be driven by a list of action objects that define a file pattern and commands to run. I want to explore using existing tools for this along the lines of Makefiles - can I put the kaku.toml config in a directory and specify target patterns using the `glob` Python module with commands to execute across each item in the returned list.

Kaku can then make use of a collection of small conversion scripts that all take the same inputs: file to act on and config block. The config block would contain the necessary items to drive the targeted conversion tool.

Directory example
```
kaku.toml
/templates/
    root.jinja
    about.jinja
    index.jinja
    post.jinja
/pages/
    site-index/
        index.asciidoc
    posts/
        *.asciidoc
    static/
        *.asciidoc
/assets/
    bear.png
    github.png
```

`kaku.toml`
```
site-url = `https://bear.im`
author = `bear`

[paths]
rootdir="/bearim/"
outputdir="output/"
templates="/templates"
images="/assets"

[rules]
[rules.site]
glob = 'pages/site-index/*.asciidoc'
target = '{stem}.html'

[rules.static]
glob = 'pages/static/**/*.asciidoc'
target = '{parent}/{stem}.html'

[rules.posts]
glob = 'pages/posts/**/*.asciidoc'
target="{parent}/{stem}.html'
```

## Generation
When a file is being processed, the source and target file is generated with a core set of variables available for expansion. Only files that have their source date/time attribute newer than the target date/time will be processed.

When files are being generated, any path that is not an absolute reference, i.e. those that do not start with `/`, will be processed using the `rootdir` value for reading and the path will be expanded with the the values from Python's `pathlib` being available for expansion and `{parent}` set as appropriate for the glob'd result, for example given the following configuration

```
[paths]
rootdir = '/sitedata/'
outputdir = 'output/'
[rules.relative]
glob = '**/*.txt'
target = '{parent}/{stem}.html'
[rules.absolute]
glob = '/foo/**/*.txt'
target = '{parent}/{stem}.html'
```

An input file of `/foo/bob/bar.txt` would result in
 - `{outputdir}`: "/foo/"
 - `{parent}`: "bob/"
 - `{name}`: "bar.txt"
 - `{stem}`: "bar"
 - `{suffix}`: ".txt"
 - target file: `/foo/bob/bar.html`

An input file of `/sitedata/bob/bar.txt` would result in
 - `{outputdir}`: "output/"
 - `{parent}`: "bob/"
 - `{name}`: "bar.txt"
 - `{stem}`: "bar"
 - `{suffix}`: ".txt"
 - target file: `/foo/bob/bar.html`

Other assumptions are in place for variable expansion
 - any input path that does not have a leading `/` will be prepended with `{rootdir}/`
 - any output path that does not have a leading `/` will be prepended with `{outputdir}/`
 - `{images-path}` will be expanded to the value of the `images` paths value relative to the output path, this allows for html and css relative paths to resolve properly
 - `{today}` will be today's date in YYYY-MM-DD format
 - `{today-year}` will be the current year
 - `{author}` will be the defined `author` configuration value
 - `{site-url}` will be the expanded to the network and url of the generated site
 - `{root}` will be the full filename incl
 - `{parent}` will be the path that the `**` glob expanded as without the root
 - `{stem}` will be the base filename without the extension
 - `{name}` will be the filename without the path
 - `{suffix}` will be the filename without the stem
