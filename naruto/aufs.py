# -*- coding: utf-8 -*-
"""
aufs code
"""
import collections
import logging
import pathlib
import re
import sh

DEV_LOGGER = logging.getLogger(__name__)
AUFS_SYS_FOLDER = pathlib.Path('/sys/fs/aufs/')
BR_REGEX = re.compile(r'^br(?P<id>\d+)$')


AUFSBranch = collections.namedtuple('AUFSBranch', 'path permission index brid si_code')


def get_aufs_branch_info_iter(si_code):
    '''
    Look up metadata around aufs
    '''
    metadata_folder = AUFS_SYS_FOLDER / ('si_' + si_code)
    if not metadata_folder.is_dir():
        raise KeyError('Unable to find metadata for {}'.format(si_code))

    for potential_branch in metadata_folder.iterdir():
        match = BR_REGEX.match(potential_branch.name)
        if match is None:
            continue

        index = int(match.group('id'))

        path_permission = (metadata_folder / 'br{}'.format(index)).open().read().strip()
        path, permission = path_permission.split('=')
        path = pathlib.Path(path)

        brid = int((metadata_folder / 'brid{}'.format(index)).open().read().strip())

        yield AUFSBranch(
            path=path, permission=permission, index=index, brid=brid, si_code=si_code)


class AUFSMount(object):
    '''
    Represent a single aufs mount
    '''
    def __init__(self, mount_entry, aufs_branches=None):
        self._mount_entry = mount_entry
        self.update(aufs_branches)

    @property
    def si_code(self):
        return self._mount_entry.mntops['si']

    @property
    def file(self):
        return pathlib.Path(self._mount_entry.file)

    def _run_mount(self, *args, **kwargs):
        sh.mount('none', str(self.file.resolve()), *args, types='aufs', **kwargs)

    def update(self, aufs_branches=None):
        '''
        Update branch info from /sys
        '''
        if aufs_branches is None:
            aufs_branches = get_aufs_branch_info_iter(self.si_code)

        self._branches = []
        for branch in aufs_branches:
            self._branches.append(AUFSMountBranch(
                self,
                branch.path,
                branch.permission,
                branch.index,
                branch.brid))

        self._branches.sort(key=lambda branch: branch.index)

    def get_branch_by_path(self, path):
        for branch in self._branches:
            if branch.path == path:
                return branch

        raise KeyError('Path {} not found in {!r}'.format(path, self))

    def unmount(self):
        DEV_LOGGER.debug('Unmounting %r', self)
        sh.umount(str(self.file.resolve()))

    def get_leaf(self):
        '''
        Get leaf of aufs mount
        '''
        return self._branches[0]


class AUFSMountBranch(object):
    '''
    Represents a single branch of AUFSMount
    '''
    def __init__(self, mount, path, permission, index, brid):
        self._mount = mount
        self._path = pathlib.Path(path)
        self._permission = permission
        assert permission in ('rw', 'ro')
        self._index = int(index)
        self._brid = int(brid)

    @property
    def index(self):
        return self._index

    @property
    def mount(self):
        return self._mount

    @property
    def mount_point(self):
        return self._mount.file

    @property
    def path(self):
        return self._path

    @property
    def permission(self):
        return self._permission

    @permission.setter
    def permission(self, permission):
        assert permission in ('rw', 'ro')
        self._mount._run_mount(
            options='remount,mod:{self._path!s}={permission}'.format(
                self=self, permission=permission))

    def delete(self):
        '''
        Delete this branch
        '''
        self._mount._run_mount(
            options='remount,del:{self._path!s}'.format(self=self))

    def insert_after(self, branch_path, permission='rw'):
        '''
        Insert new branch after this one
        '''
        self._mount._run_mount(
            options='remount,add:{index}:{branch_path!s}={permission}'.format(
                index=self._index, branch_path=branch_path, permission=permission))

    def __str__(self):
        return '{self._path} on {self._mount.file}'.format(self=self)
