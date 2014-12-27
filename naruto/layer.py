# -*- coding: utf-8 -*-
"""
Main naruto code
"""
import collections
import collections.abc
import contextlib
import itertools
import json
import logging
import os
import pathlib
import re
import uuid

import naruto.aufs
import naruto.mount

DEV_LOGGER = logging.getLogger(__name__)

CHILDREN_SUBDIR = 'children'
CONTENTS_SUBDIR = 'contents'
METADATA_NAME = 'naruto_metadata.json'


def _get_aufs_mount_info_iter():
    '''
    Get all aufs mount info
    '''
    for mount in naruto.mount.get_mounts_iter():
        if mount.vfstype != 'aufs':
            continue
        yield naruto.aufs.AUFSMount(mount)


def create_file(file_path):
    '''
    Create and open a file but only if it doesnt exist
    >>> import tempfile
    >>> test_dir = tempfile.TemporaryDirectory()
    >>> test_file = pathlib.Path(test_dir.name) / 'test'
    >>> file_1 = create_file(test_file)
    >>> file_2 = create_file(test_file) # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    FileExistsError: [Errno 17] File exists: '/tmp/tmpjjl1ap9q/test'
    '''
    # If private key doesn't exist
    # This odd method of opening the file should ensure we don't
    # get races
    filedesc = os.open(
        str(file_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL)

    return os.fdopen(filedesc, 'w')


class LayerNotFound(Exception):
    pass


class NarutoLayer(collections.abc.Iterable):
    '''
    Naruto Layer


    Directory Layout
    ----------------

    <layer_id>/
      +--contents/ -- Directory with file contents of layer
      +--children/ -- Child layers
      +--naruto_metadata.json -- Metadata about layer
    '''
    def __init__(self, layer_dir):
        self._layer_dir = pathlib.Path(layer_dir).resolve()
        DEV_LOGGER.debug('Loading layer in %r', self._layer_dir)

        self._children_path = self._layer_dir / CHILDREN_SUBDIR
        self._contents_path = self._layer_dir / CONTENTS_SUBDIR
        self._metadata_path = self._layer_dir / METADATA_NAME

        for path in (self._children_path, self._contents_path):
            if not path.is_dir():
                raise ValueError('Expected {} to be directory'.format(path))

        for path in (self._metadata_path,):
            if not path.is_file():
                raise ValueError('Expected {} to be file'.format(path))

    def __eq__(self, other):
        return self._layer_dir == other._layer_dir

    def __iter__(self):
        '''
        Iterator over children
        '''
        return self.iter_children()

    def iter_children(self):
        '''
        Iterate over all direct children
        '''
        for child in self._children_path.iterdir():
            if child.is_dir():
                yield self.__class__(child)

    def iter_descendants(self):
        '''
        Iterate over all descendants recursively
        '''
        for child in self.iter_children():
            yield child
            for descendant in child.iter_descendants():
                yield descendant

    def __repr__(self):
        return (
            '{self.__class__.__module__}.{self.__class__.__name__}'
            '({self._layer_dir!r})'.format(
                self=self))

    def __str__(self):
        return (
            'NarutoLayer('
            'id={self.layer_id}, '
            'description={self.description}, '
            'tags={tags}, '
            'children={children}, descendants={descendants})').format(
                self=self,
                children=len(self.children),
                descendants=len(self.descendants),
                tags=tuple(self.tags))

    def get_metadata(self):
        '''
        Get metadata dict
        '''
        return json.load(self._metadata_path.open('r'))

    @contextlib.contextmanager
    def _get_metadata_context(self):
        '''
        Conveniant context to update metadata
        '''
        metadata = self.get_metadata()
        yield metadata
        json.dump(metadata, self._metadata_path.open('w'))

    @property
    def description(self):
        return self.get_metadata()['description']

    @description.setter
    def description(self, value):
        with self._get_metadata_context() as metadata:
            metadata['description'] = str(value)

    @property
    def tags(self):
        '''
        Tags is a set of useful strings used to tag a layer for searching or organisation
        '''
        return frozenset(self.get_metadata().get('tags', ()))

    @tags.setter
    def tags(self, tags):
        '''
        Tags is a set of useful strings used to tag a layer for searching or organisation
        '''
        with self._get_metadata_context() as metadata:
            metadata['tags'] = tuple(set(str(value) for value in tags))

    @property
    def has_children(self):
        '''
        Does this have children
        '''
        return next(iter(self), None) is not None

    @property
    def contents_path(self):
        '''
        RO access to contents path
        '''
        return self._contents_path

    # All lead-nodes should be read only
    read_only = has_children

    @property
    def is_root(self):
        '''
        RO property for is_root
        '''
        return self.get_metadata()['is_root']

    @property
    def mounted(self):
        '''
        Is layer mounted
        '''
        return next(self.find_mounted_branches_iter(), None) is not None

    @property
    def layer_id(self):
        '''
        Return layer id
        '''
        return self._layer_dir.name

    @property
    def path(self):
        return self._layer_dir

    @property
    def children(self):
        '''
        Direct children
        '''
        return tuple(self.iter_children())

    @property
    def descendants(self):
        '''
        All descendants
        '''
        return tuple(self.iter_descendants())

    def get_layer_permissions(self):
        '''
        Get layer permissions for self and parents
        '''
        my_perms = (self._contents_path, 'ro' if self.read_only else 'rw')

        if self.is_root:
            return [my_perms, ]
        else:
            parent_branches = self.parent.get_layer_permissions()
            return [my_perms] + parent_branches

    def get_root(self):
        '''
        Find root layer
        '''
        if self.is_root:
            return self
        else:
            return self.parent.get_root()

    @classmethod
    def create(cls, parent_directory, is_root=True, description=''):
        '''
        Create new NarutoLayer
        '''
        parent_directory = pathlib.Path(parent_directory)

        if not is_root:
            # Check that parent is valid
            cls(parent_directory.parent)

        if not description and is_root:
            description = 'root'

        sub_layer_uuid = str(uuid.uuid4()).replace('-', '')
        sub_layer_dir = parent_directory / sub_layer_uuid
        sub_layer_dir.mkdir()

        for subdir in (CHILDREN_SUBDIR, CONTENTS_SUBDIR):
            (sub_layer_dir / subdir).mkdir()

        initial_metadata = {
            'is_root': is_root,
            'description': description
        }

        json.dump(initial_metadata, create_file(sub_layer_dir / METADATA_NAME))

        DEV_LOGGER.info('Create empty layer in %r', sub_layer_dir)

        return cls(sub_layer_dir)

    @classmethod
    def find_layer_mounted_at_dest(cls, destination):
        '''
        Find layer mounted at dest
        '''
        mount_info = naruto.mount.find_mount_by_dest(destination)

        if mount_info.vfstype != 'aufs':
            raise LayerNotFound(
                'Destination {!r} is not an aufs mount point'.format(destination))

        aufs_mount = naruto.aufs.AUFSMount(mount_info)
        leaf_branch = aufs_mount.get_leaf()

        return cls(pathlib.Path(leaf_branch.path).parent)

    def _create_child(self, description=''):
        '''
        Create new child
        '''
        DEV_LOGGER.info('Create child of %r', self)
        return self.__class__.create(self._children_path, is_root=False, description=description)

    def create_child(self, description=''):
        '''
        Create new child but freeze existing mounts first
        '''
        self.freeze_mounts()
        return self._create_child(description=description)

    @property
    def parent(self):
        '''
        Get parent
        '''
        if self.is_root:
            return None

        parent_dir = self._layer_dir.parent.parent

        DEV_LOGGER.debug('Parent of %r is at %r', self, parent_dir)
        return self.__class__(parent_dir)

    def mount(self, destination):
        '''
        Mount this layer
        '''
        destination = pathlib.Path(destination)
        DEV_LOGGER.info('Mounting layer %r on %r', self, destination)

        if not destination.is_dir() and next(destination, None) is not None:
            raise Exception('{} must be directory and must be empty'.format(destination))

        branches = self.get_layer_permissions()

        # There should only be one rw branch
        assert all(permission == 'ro' for _path, permission in branches[1:])

        branch_strings = [
            '{path!s}={permission}'.format(path=path.resolve(), permission=permission)
            for path, permission in branches]
        branch_string = 'br:{}'.format(':'.join(branch_strings))
        mount_point = str(destination.resolve())

        DEV_LOGGER.debug('Using branches %r. Mount point %r', branch_string, mount_point)
        naruto.mount.mount('none', mount_point, types='aufs', options=branch_string)

    def find_mounted_branches_iter(self):
        '''
        Find if this is mounted
        '''
        for aufs_mount in _get_aufs_mount_info_iter():
            try:
                yield aufs_mount.get_branch_by_path(self._contents_path)
            except KeyError:
                continue

    def unmount_all(self):
        '''
        Unmount all locations this is mounted
        '''
        DEV_LOGGER.info('Attempting to umount all uses of %r', self)
        for aufs_mount_branch in self.find_mounted_branches_iter():
            DEV_LOGGER.info('Unmounting %s', aufs_mount_branch)
            aufs_mount_branch.mount.unmount()

    def freeze_mounts(self, preserve_rw=True):
        '''
        All mounts currently using this layer rw should be moved to new child layer
        '''
        DEV_LOGGER.info('Freezing mounts for %r', self)
        child = None

        for aufs_mount_branch in self.find_mounted_branches_iter():
            if aufs_mount_branch.permission == 'ro':
                DEV_LOGGER.debug('Branch %r is already ro', aufs_mount_branch)
                continue

            DEV_LOGGER.debug('Branch %r is rw. Remounting.', aufs_mount_branch)
            aufs_mount_branch.permission = 'ro'

            if preserve_rw:
                if child is None:
                    child = self._create_child()
                DEV_LOGGER.debug(
                    'Preserving rw for branch %r. Using new child %r', aufs_mount_branch, child)
                aufs_mount_branch.insert_after(child.contents_path, 'rw')

        self._validate()

    def _validate(self):
        '''
        Do some self checks to ensure everything is as expected
        '''
        if self.read_only:
            for aufs_mount_branch in self.find_mounted_branches_iter():
                if aufs_mount_branch.permission != 'ro':
                    raise Exception(
                        'All mounts should be ro. Got {!r}'.format(aufs_mount_branch))

    LAYER_REL_RE = re.compile(r'(?P<command>[\^?\~\@])(?P<depth>\d*)')
    LAYER_SPEC_RE = re.compile(r'(?P<reference>[^?\~\^\@]*)(?P<rel_spec>.*)')

    def find_layer(self, layer_spec):
        '''
        Find layer by spec
        '''
        layer_spec = layer_spec.strip()

        layer_match = self.LAYER_SPEC_RE.match(layer_spec)
        if not layer_match:
            raise ValueError('Incorrectly syntax in layer spec: {}'.format(layer_spec))

        layer_reference = layer_match.group('reference')
        rel_spec = layer_match.group('rel_spec')

        DEV_LOGGER.debug(
            'Finding layer. layer_reference=%r rel_spec=%r', layer_reference, rel_spec)

        root_layer = self.get_root()
        if layer_reference == 'root':
            layer = root_layer
        elif layer_reference == '':
            layer = self
        else:
            DEV_LOGGER.debug('Trying to find layer with tag or reference: %r', layer_reference)
            for layer in itertools.chain((root_layer, ), root_layer.iter_descendants()):
                DEV_LOGGER.debug('Considering %s', layer)
                if layer_reference == layer.layer_id or layer_reference in layer.tags:
                    DEV_LOGGER.debug('Found reference in %s', layer)
                    break
            else:
                raise KeyError('Unable to find layer {}'.format(layer_reference))

        for match in self.LAYER_REL_RE.finditer(rel_spec):
            command = match.group('command')
            depth = match.group('depth')
            if depth == '':
                depth = 1
            else:
                depth = int(depth)

            new_layer = layer._resolve_single_rel_spec(command, depth)
            DEV_LOGGER.debug('Resolving %r %r on %r got %r', command, depth, layer, new_layer)
            layer = new_layer

        return layer

    def _resolve_single_rel_spec(self, command, depth):
        '''
        Resolve single rel spec relative to this layer
        '''
        assert depth > 0
        if command == '^':
            for index, child in enumerate(self, 1):
                if index == depth:
                    return child
            else:
                raise KeyError('Couldn\'t find {} child of {}'.format(depth, self))
        elif command == '~':
            current_layer = self
            for _ in range(depth):
                current_layer = next(iter(current_layer))
            return current_layer
        elif command == '@':
            current_layer = self
            for _ in range(depth):
                current_layer = current_layer.parent
            return current_layer
