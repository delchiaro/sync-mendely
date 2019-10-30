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
parser.add_argument('-remote', dest='rem', help='Folder with annotated PDFs synced to remote location (e.g. Google Drive)', required=True)
parser.add_argument('-dry', dest='dry', action='store_true', help='Dry run (don\'t copy pdfs)')
parser.add_argument('-lr', dest='lr', action='store_true', help='Only sync local -> remote')
parser.add_argument('-rl', dest='rl', action='store_true', help='Only sync remote -> local')
parser.add_argument('-th', dest='threshold', action='store', help='String matching threshold, float value between 0.0 and 1.0 (default: 0.92)',
                    default=0.92)
parser.add_argument('-v', dest='verbose', help='Verbose mode (also show info about correctly matched files)', action='store_true')
# parser.add_argument('-cache', dest='cache', help='Cache file', default=None)

args = parser.parse_args()
if args.lr and args.rl:
    print('-lr and -rl should be mutally exclusive. Assuming both ways are wanted...')
if not args.lr and not args.rl:
    args.lr = True
    args.rl = True

# List Local files
local_files = glob.glob(args.loc + '/*[Pp][Dd][Ff]')
local_files = sorted([str.replace(filen, args.loc + '/', '') for filen in local_files])
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
remote_files = sorted([str.replace(filen, args.rem + '/', '') for filen in remote_files])
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
    cache = {'oldfiles': [], 'rlpairs': {}, 'matched_remote': []}


def vprint(s: str):
    if args.verbose:
        print(s)


def compute_score(local_info, remote_info):
    title_score = SequenceMatcher(None, local_info[TITLE_KEY].lower(), remote_info[TITLE_KEY].lower()).ratio()
    author_score = SequenceMatcher(None, local_info[MAIN_AUTHOR_KEY].lower(), remote_info[MAIN_AUTHOR_KEY].lower()).ratio()
    author_score_wo_et_al = SequenceMatcher(None, local_info[MAIN_AUTHOR_KEY].lower().split(' et al.')[0],
                                            remote_info[MAIN_AUTHOR_KEY].lower().split(' et al.')[0]).ratio()
    author_score = max(author_score, author_score_wo_et_al)

    year_score = SequenceMatcher(None, local_info[YEAR_KEY].lower(), remote_info[YEAR_KEY].lower()).ratio()
    return .85 * title_score + .1 * author_score + .05 * year_score


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

        if local_f_converted in remote_files:
            if local_f_converted in cache['rlpairs'].keys():
                print(f' - WARNING: LOCAL FILE   `{local_f}`\n'
                      f'            CONVERTED TO `{local_f_converted}`\n'
                      f'            BUT CONVERTED NAME IS ALREADY MATCHED BY LOCAL FILE: `{cache["rlpairs"][local_f_converted]}` (THIS FILE IS STEALING THE OLD MATCH!!)\n')
                cache['rlpairs'][local_f_converted] = local_f

            else:
                vprint(f' + LOCAL FILE:      `{local_f}`\n'
                       f'   MATCHED REMOTE:  `{local_f_converted}`\n')
                # cache['oldfiles'].append(local_f)
                cache['rlpairs'][local_f_converted] = local_f

            # cache['matched_remote'].append(local_f_converted)

        else:  # elif local_f not in cache['oldfiles']:
            best = ''
            bestscore = 0
            for remote_f, remote_info in remote_dict.items():
                score = compute_score(local_info, remote_info)
                # score = SequenceMatcher(None, remote_f.lower(), local_f_converted.lower()).ratio()
                # score = SequenceMatcher(None, remote_f.lower(), local_f_converted.lower()).ratio()
                if score > bestscore:
                    bestscore = score
                    best = remote_f

            if bestscore >= args.threshold:
                if local_f_converted in cache['rlpairs'].keys():
                    print(f' - WARNING: LOCAL FILE:  `{local_f}`\n'
                          f'            MATCHED TO:  `{best}`\n'
                          f'            BUT MATCHED NAME WAS ALREADY MATCHED BY LOCAL FILE: `{cache["rlpairs"]}`\n')
                else:
                    vprint(f' + LOCAL FILE:     `{local_f}`')
                    vprint(f'   BEST REMOTE:    `{best}`')
                    vprint(f'   MATCHED WITH SCORE {bestscore}\n')
                    # cache['oldfiles'].append(local_f)
                    cache['rlpairs'][best] = local_f

            else:
                print(f' - LOCAL FILE:     `{local_f}`')
                print(f'   BEST REMOTE:    `{best}`')
                print(f'   DISCARTED WITH SCORE {bestscore} (IS UNDER THE THRESHOLD {args.threshold})')
                print(f'   +++ CONSIDERED A NEW ONE, MAPPING TO: {local_f_converted}\n')
                cache['rlpairs'][local_f_converted] = local_f

processed = []
if args.rl:
    print('\n\n\n')
    print('=== **************************************** ===')
    print('=== CHECK FOR REMOTE FILES TO UPDATE LOCALLY ===')
    print('=== **************************************** ===\n')
    for remote_f, remote_info in remote_dict.items():

        if remote_f in cache['rlpairs']:
            best = cache['rlpairs'][remote_f]
            processed.append(best)
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
            if bestscore < args.threshold:
                print(f' - REMOTE FILE:  `{remote_f}`')
                print(f'   BEST LOCAL:   `{best}`')
                print(f'   DISCARTED WITH SCORE {bestscore} (IS UNDER THE THRESHOLD {args.threshold})\n')
                continue
            else:
                if remote_f in cache['rlpairs'].keys():
                    print(f' - WARNING: REMOTE FILE:  `{remote_f}`\n'
                          f'            MATCHED TO:   `{best}`\n'
                          f'            BUT MATCHED NAME WAS ALREADY MATCHED BY LOCAL FILE: `{cache["rlpairs"]}`\n')
                else:
                    vprint(f' + REMOTE FILE:    `{remote_f}`')
                    vprint(f'   BEST LOCAL:     `{best}`')
                    vprint(f'   MATCHED WITH SCORE {bestscore}\n')
                    # cache['oldfiles'].append(local_f)
                    cache['rlpairs'][remote_f] = best

print('\n\n\n')
print('=== **************************************** ===')
print('===              COPYING FILES               ===')
print('=== **************************************** ===\n')


def copy(local_file, remote_file, mode):
    prepend = "(DRY/FAKE)" if args.dry else ""
    if mode is 'l2r':
        print(f"{prepend}Copy local to remote: {local_file}  -->  {remote_file}")
        if not args.dry:
            copyfile(args.loc + '/' + local_file, args.rem + '/' + remote_file)
    elif mode is 'r2l':
        print(f"{prepend}Copy remote to local: {remote_file}  -->  {local_file}")
        if not args.dry:
            copyfile(args.loc + '/' + local_file, args.rem + '/' + remote_file)


for remote_f, local_f in cache['rlpairs'].items():
    # Get file sizes
    # loc_time = os.path.getctime(args.loc + '/' + local_f)
    # rem_time = os.path.getctime(args.rem + '/' + remote_f)
    try:
        loc_size = os.path.getsize(args.loc + '/' + local_f)
    except:
        loc_size = None
    try:
        rem_size = os.path.getsize(args.rem + '/' + remote_f)
    except:
        rem_size = None

    if rem_size is None and loc_size is None:
        print('\nUNKOWN ERROR (rem_size is None, loc_size is None)')

    elif rem_size is None and loc_size is not None:  # new local file to be copied in remote
        if args.lr:
            print('\nNew local file will be added in remote: ')
            copy(local_f, remote_f, 'l2r')

    elif rem_size is not None and loc_size is None:  # new remote file to be copied in local
        if args.rl:
            print('\nNew remote file will be added in local: ')
            copy(local_f, remote_f, 'r2l')

    else:
        if loc_size != rem_size and args.rl:
            print(f'\nDifferent remote version will be copied in local (remote size: {rem_size}, local size: {loc_size}')
            copy(local_f, remote_f, 'r2l')

# # Save cache
# if args.cache is not None:
#     pickle.dump(cache, open(args.cache, "wb"))
#     print('Cache saved')
# else:
#     print('Cache NOT saved (use -cache <filename> option to save cache!)')
