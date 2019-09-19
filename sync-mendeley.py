import glob
import argparse
from difflib import SequenceMatcher
import pickle
import os
from enum import Enum
from shutil import copyfile

AUTHOR_KEY = 'author'
MAIN_AUTHOR_KEY = 'main_author'
YEAR_KEY = 'year'
TITLE_KEY = 'title'

DESKTOP_SPLIT_MODE = [AUTHOR_KEY, YEAR_KEY, TITLE_KEY]
ANDROID_SPLIT_MODE = [AUTHOR_KEY, YEAR_KEY, TITLE_KEY]
DEFAULT_SEPARATOR = ' - '


class Target(Enum):
    desktop = 0
    android = 1


class PaperInfoError(RuntimeError):
    def __init__(self, fname):
        super().__init__()
        self.fname = fname


def paper_info(fname, target: Target, separator=DEFAULT_SEPARATOR):
    if target is Target.android:
        split_mode = ANDROID_SPLIT_MODE
    elif target is Target.desktop:
        split_mode = DESKTOP_SPLIT_MODE
    else:
        raise ValueError()
    # print("fname: " + fname)
    try:
        dot_split = fname.split('.')
        # ext = dot_split[-1]
        name = '.'.join(dot_split[:-1])
        info_split = name.split(separator)
        info_split[2] = separator.join(info_split[2:])
        info_split = {m: info for m, info in zip(split_mode[:len(info_split)], info_split)}
    except IndexError as e:
        raise PaperInfoError(fname)
    info_split[MAIN_AUTHOR_KEY] = info_split[AUTHOR_KEY].split(',')[0]
    return info_split


def desktop2android(fname, info=None, separator=DEFAULT_SEPARATOR):
    if info is None:
        info = paper_info(fname, Target.desktop)
    ext = fname.split('.')[-1]
    # print(info)
    converted_author = ''
    converted_year = ''
    converted_title = ''

    if info[AUTHOR_KEY].lower() is not 'unknown':
        converted_author = info['author'].split(' ')[0].split(',')[0].split('.')[0]

    if info[YEAR_KEY].lower() is not 'unknown':
        converted_year = info['year']

    if info[TITLE_KEY].lower() is not 'unknown':
        converted_title = info['title'].replace('_', ': ').replace(': : ', '__')

    # print("author: " + converted_author)
    # print("title: " + converted_title)
    sep1 = separator if (converted_author != '' and converted_year != '') else ''
    sep2 = separator if ((converted_author != '' or converted_year != '') and converted_title != '') else ''
    fname = converted_author + sep1 + converted_year + sep2 + converted_title + '.' + ext
    return fname


parser = argparse.ArgumentParser(description='Sync PDF files between local and remote folders with file name matching.')
parser.add_argument('-local', dest='loc', help='Local folder with Mendeley PDFs', required=True)
parser.add_argument('-remote', dest='rem', help='Folder with annotated PDFs synced to remote location (e.g. Google Drive, Dropbox)',
                    required=True)
parser.add_argument('-cache', dest='cache', help='Cache file', default=None)
parser.add_argument('-dry', dest='dry', action='store_true', help='Dry run (don\'t copy pdfs)')
parser.add_argument('-lr', dest='lr', action='store_true', help='Only sync local -> remote')
parser.add_argument('-rl', dest='rl', action='store_true', help='Only sync remote -> local')

args = parser.parse_args()
if args.lr and args.rl:
    print('-lr and -rl should be mutally exclusive. Assuming both ways are wanted...')
if not args.lr and not args.rl:
    args.lr = True
    args.rl = True

# List Local files
local_files = glob.glob(args.loc + '/*[Pp][Dd][Ff]')
local_files = [str.replace(filen, args.loc + '/', '') for filen in local_files]
local_dict = {}
for local_f in local_files:
    try:
        info = paper_info(local_f, Target.desktop)
    except PaperInfoError:
        print(f"\nWARNING: Local file ``{local_f}`` doesn't have a valid name... skip\n")
        continue
    local_dict[local_f] = info

# List Remote files
remote_files = glob.glob(args.rem + '/*[Pp][Dd][Ff]')
remote_files = [str.replace(filen, args.rem + '/', '') for filen in remote_files]
remote_dict = {}
for remote_f in remote_files:
    try:
        info = paper_info(remote_f, Target.android)
    except PaperInfoError:
        print(f"\nWARNING: Remote file ``{remote_f}`` doesn't have a valid name... skip\n")
        continue
    remote_dict[remote_f] = info

# Load cache file
if args.cache is not None and os.path.isfile(args.cache):
    cache = pickle.load(open(args.cache, "rb"))
    print('Cache loaded')
else:
    cache = {'oldfiles': [], 'rlpairs': {}}



def compute_score(local_info, remote_info):
    title_score = SequenceMatcher(None, local_info[TITLE_KEY].lower(), remote_info[TITLE_KEY].lower()).ratio()
    author_score = SequenceMatcher(None, local_info[MAIN_AUTHOR_KEY].lower(), remote_info[MAIN_AUTHOR_KEY].lower()).ratio()
    year_score = SequenceMatcher(None, local_info[YEAR_KEY].lower(), remote_info[YEAR_KEY].lower()).ratio()
    return .8 * title_score + .15 * author_score + .05 * year_score


if args.lr:
    # Local to remote: copy new files only
    # Don't copy if exists or in cache
    # If name match and not in cache, put in cache
    print('\n\n\n')
    print('=== *************************************** ===')
    print('=== CHECK FOR NEW FILES IN THE LOCAL FOLDER ===')
    print('=== *************************************** ===\n')
    for local_f, local_info in local_dict.items():
        local_f_converted = desktop2android(local_f, local_info)

        if local_f_converted not in remote_files and local_f not in cache['oldfiles']:
            best = ''
            bestscore = 0
            for remote_f, remote_info in remote_dict.items():
                score = compute_score(local_info, remote_info)
                # score = SequenceMatcher(None, remote_f.lower(), local_f_converted.lower()).ratio()
                # score = SequenceMatcher(None, remote_f.lower(), local_f_converted.lower()).ratio()
                if score > bestscore:
                    bestscore = score
                    best = remote_f

            if bestscore < .9:
                print(f' - NEW LOCAL FILE:     `{local_f}`')
                print(f'   TARGET REMOTE:      `{best}`\n')
                if not args.dry:
                    copyfile(args.loc + '/' + local_f, args.rem + '/' + local_f_converted)
                    cache['oldfiles'].append(local_f)
            else:
                print(f' - MATCHED LOCAL FILE: `{local_f}`')
                print(f'   MATCHED REMOTE:     `{best}`\n')
                cache['oldfiles'].append(local_f)

if args.rl:
    print('\n\n\n')
    print('=== **************************************** ===')
    print('=== CHECK FOR REMOTE FILES TO UPDATE LOCALLY ===')
    print('=== **************************************** ===\n')
    for remote_f, remote_info in remote_dict.items():

        if remote_f in cache['rlpairs']:
            best = cache['rlpairs'][remote_f]
        else:
            filen = str.replace(remote_f, '..', '.')
            filen = str.replace(filen, '_', '')
            filen = filen.lower()
            best = ''
            bestscore = 0
            for local_f, local_info in local_dict.items():
                score = compute_score(local_info, remote_info)
                if score > bestscore:
                    bestscore = score
                    best = local_f
            if bestscore < .9:
                print(f"\n  WARNING - NO MATCH:   `{filen}`")
                print(f"DISCARDED BEST MATCH:   `{best}`")
                continue
            cache['rlpairs'][remote_f] = best
        # Get file sizes
        loc_size = os.path.getsize(args.loc + '/' + best)
        rem_size = os.path.getsize(args.rem + '/' + remote_f)

        # If different cp from remote to local
        if loc_size != rem_size:
            if args.dry:
                print("Copy " + remote_f + ' to ' + best)
            else:
                copyfile(args.rem + '/' + remote_f, args.loc + '/' + best)

# Save cache
if args.cache is not None:
    pickle.dump(cache, open(args.cache, "wb"))
    print('Cache saved')
else:
    print('Cache NOT saved (use -cache <filename> option to save cache!)')
