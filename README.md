This repo is a [fork of this project](http://jmonlong.github.io/Hippocamplus/2018/09/22/sync-mendeley/).

To update a local folder (`-local`) and a folder synced to the remote location (`-remote`) like Google Drive.
More information on 
```sh
python sync-mendeley.py -local PATH/TO/MendeleyDesktop -remote PATH/TO/GoogleDrive/ArticlesPDF
```

*I tend to do a dry run first using `-dry`.*

Usage:

```txt
usage: sync-mendeley.py [-h] -local LOC -remote REM [-dry] [-lr] [-rl]
                        [-th THRESHOLD] [-v]

Sync PDF files between local and remote folders with file name matching.

optional arguments:
  -h, --help     show this help message and exit
  -local LOC     Local folder with Mendeley PDFs
  -remote REM    Folder with annotated PDFs synced to remote location (Google
                 Drive, Dropbox, ...)
  -dry           Dry run (don't copy pdfs)
  -lr            Only sync local -> remote
  -rl            Only sync remote -> local
  -th THRESHOLD  String matching threshold, float value between 0.0 and 1.0
                 (default: 0.92)
  -v             Verbose mode (also show info about correctly matched files)
```
