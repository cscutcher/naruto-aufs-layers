# -*- coding: utf-8 -*-
"""
Code to parse mount information
"""
import collections
import logging
import pathlib
import sh
import functools

DEV_LOGGER = logging.getLogger(__name__)


class NoMountPermissions(Exception):
    '''
    Exception when we cant mount for permission issues
    '''


def _wrap_permissions(command):
    ''' Wrap mount calls with error handler for permissions'''

    @functools.wraps(command)
    def wrapped(*args, **kwargs):
        try:
            return command(*args, **kwargs)
        except sh.ErrorReturnCode as error:
            if error.exit_code == 1:
                raise NoMountPermissions(error)
            raise
    return wrapped

sudo = sh.sudo.bake(non_interactive=True)
mount = _wrap_permissions(sudo.mount)
umount = _wrap_permissions(sudo.umount)

MountEntry = collections.namedtuple('MountEntry', 'spec file vfstype mntops freq passno')


def _parse_mount_line(line):
    '''
    Convert line from /proc/mounts to MountEntry

    >>> entry = _parse_mount_line(\
        'udev /dev devtmpfs rw,relatime,size=8187468k,nr_inodes=2046867,mode=755 0 0')
    >>> entry.spec
    'udev'
    >>> entry.file
    '/dev'
    >>> entry.vfstype
    'devtmpfs'
    >>> 'rw' in entry.mntops
    True
    >>> entry.mntops['size']
    '8187468k'
    >>> entry.freq
    '0'
    >>> entry.passno
    '0'

    '''
    cols = line.split(' ')

    # Now split opts
    mntopts = cols[3].split(',')
    mntopts_dict = {}
    for opt in mntopts:
        key, sep, value = opt.partition('=')
        if not sep:
            mntopts_dict[key] = None
        else:
            mntopts_dict[key] = value
    cols[3] = mntopts_dict

    return MountEntry(*cols)

MOCK_PROC_MOUNTS = '''
    rootfs / rootfs rw 0 0
    sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0
    proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
    udev /dev devtmpfs rw,relatime,size=8187468k,nr_inodes=2046867,mode=755 0 0
    devpts /dev/pts devpts rw,nosuid,noexec,relatime,gid=5,mode=620,ptmxmode=000 0 0
    tmpfs /run tmpfs rw,nosuid,noexec,relatime,size=1640648k,mode=755 0 0'''


def get_mounts_iter(mount_file_contents=None):
    '''
    Parse /proc/mounts and return iterator of mounts

    >>> entries = list(get_mounts_iter(MOCK_PROC_MOUNTS))
    >>> udev_entry = entries[3]
    >>> udev_entry.spec
    'udev'
    >>> udev_entry.file
    '/dev'
    >>> udev_entry.vfstype
    'devtmpfs'
    >>> 'rw' in udev_entry.mntops
    True
    >>> udev_entry.mntops['size']
    '8187468k'
    >>> udev_entry.freq
    '0'
    >>> udev_entry.passno
    '0'

    '''
    _mount_file_contents = (
        open('/proc/mounts').read() if mount_file_contents is None else mount_file_contents)

    return (
        _parse_mount_line(line.strip()) for line in _mount_file_contents.splitlines() if line)


def find_mount_by_dest(dest, mount_file_contents=None):
    '''
    Find a mounted path by destination.

    >>> find_mount_by_dest('/geoff', MOCK_PROC_MOUNTS).file
    '/'
    >>> find_mount_by_dest('/proc', MOCK_PROC_MOUNTS).file
    '/proc'

    Should return the 'nearest' mount. Both these examples might end up returning the root mount
    >>> find_mount_by_dest('/proc/geoff', MOCK_PROC_MOUNTS).file
    '/proc'
    >>> find_mount_by_dest('/dev/pts/blah', MOCK_PROC_MOUNTS).file
    '/dev/pts'

    The unlikely event that there's no matching mount you'll get a KeyError:
    >>> find_mount_by_dest('/geoff', '')
    Traceback (most recent call last):
        ...
    KeyError: 'Unable to find mount for /geoff'
    '''
    dest = pathlib.Path(dest)

    try:
        dest = dest.resolve()
    except FileNotFoundError:
        # If we can't resolve path that it's ok.
        pass

    matches = []

    for mount in get_mounts_iter(mount_file_contents=mount_file_contents):
        mount_file = pathlib.Path(mount.file)
        try:
            relative_path = dest.relative_to(mount_file)
        except ValueError:
            continue
        matches.append((mount, relative_path))

    if not matches:
        raise KeyError('Unable to find mount for {}'.format(dest))

    matches.sort(key=lambda match: len(match[1].parts))

    return matches[0][0]
