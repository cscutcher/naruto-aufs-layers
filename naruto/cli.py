# -*- coding: utf-8 -*-
"""
Commands for cli
"""
import io
import logging
import os
import os.path
import pathlib
import shutil

import click

from naruto import NarutoLayer

DEV_LOGGER = logging.getLogger(__name__)
_DEFAULT_NARUTO_DIR = '~/.naruto/'


@click.group()
@click.option('-V', '--verbosity', type=int, help='Verbosity of logging', default=logging.INFO)
def cli(verbosity):
    '''
    Naruto CLI
    '''
    DEV_LOGGER.debug('Verbosity is %r', verbosity)
    logging.basicConfig(level=verbosity)


class _LayerLookup(click.ParamType):
    '''
    Type which loads naruto dir
    '''
    name = 'NarutoDir'

    def __init__(self, allow_discovery=True):
        self._allow_discovery = allow_discovery

    def convert(self, value, param, context):
        '''
        Parse Naruto argument
        '''
        DEV_LOGGER.debug('Trying to find root layer for value %r', value)

        root_spec, _, layer_spec = value.partition(':')

        if not root_spec and self._allow_discovery:
            layer = NarutoLayer.find_layer_mounted_at_dest(pathlib.Path(os.getcwd()))
        else:
            if os.sep in root_spec:
                naruto_root = pathlib.Path(root_spec)
            else:
                naruto_root = pathlib.Path(os.path.expanduser(_DEFAULT_NARUTO_DIR)) / root_spec

            naruto_root, = tuple(naruto_root.iterdir())

            layer = NarutoLayer(naruto_root)

        if layer_spec:
            layer = layer.find_layer(layer_spec)

        DEV_LOGGER.debug('Parsed layer at %r from cli', layer)
        return layer


@cli.command()
@click.argument('name_or_path')
@click.option(
    '--is_path', help='Create by full path instead of name in {}'.format(_DEFAULT_NARUTO_DIR))
@click.option('--description', help='Add description to new naruto layer')
def create(name_or_path, is_path, description):
    '''
    Create new NarutoLayer
    '''
    if is_path:
        path = pathlib.Path(name_or_path)
    else:
        home_naruto_dir = pathlib.Path(os.path.expanduser(_DEFAULT_NARUTO_DIR))
        if not home_naruto_dir.is_dir():
            home_naruto_dir.mkdir()
        home_naruto_dir = home_naruto_dir.resolve()

        path = home_naruto_dir / name_or_path
        if not path.is_dir():
            path.mkdir()

        # Check nothing nasty from user
        assert path.parent == home_naruto_dir

        if len(tuple(path.iterdir())) != 0:
            raise Exception('Expected create directory {!s} to be empty'.format(path))

    NarutoLayer.create(path, description=description)


class InfoNodeAdapter(object):
    '''
    Adapt NarutoLayer for info printout
    '''
    def __init__(self, layer):
        self._layer = layer

    def output(self, io_stream, level, highlight):
        io_stream.write('{indent}+-- {highlight}{layer!s}{highlight}\n'.format(
            indent='  ' * level,
            layer=self._layer,
            highlight='!!!!' if self._layer in highlight else ''))
        for child in self._layer:
            self.__class__(child).output(io_stream, level + 1, highlight)


LAYER_OPT = click.option('-l', '--naruto_layer', type=_LayerLookup(), default='')


@cli.command()
@LAYER_OPT
def info(naruto_layer):
    '''
    Get info about a layer
    '''
    io_stream = io.StringIO()
    InfoNodeAdapter(naruto_layer.get_root()).output(io_stream, 0, highlight=(naruto_layer,))
    click.echo(io_stream.getvalue())


@cli.command()
@LAYER_OPT
@click.argument('mount_dest')
def mount(naruto_layer, mount_dest):
    '''
    Mount a layer
    '''
    naruto_layer.mount(mount_dest)


@cli.command()
@LAYER_OPT
@click.argument('mount_dest')
@click.option('--description', help='Add description to new naruto layer')
def branch_and_mount(naruto_layer, mount_dest, description):
    '''
    Branch a layer and mount at new dest
    '''
    naruto_layer.create_child(description=description).mount(mount_dest)


@cli.command()
@LAYER_OPT
def unmount_all(naruto_layer):
    '''
    Unmount all uses of this layer
    '''
    naruto_layer.unmount_all()


@cli.command()
@LAYER_OPT
def find_mounts(naruto_layer):
    '''
    Find where layer is mounted
    '''
    for branch in naruto_layer.find_mounted_branches_iter():
        click.echo('{branch.path}={branch.permission} at {branch.mount_point}'.format(
            branch=branch))


@cli.command()
@LAYER_OPT
def delete(naruto_layer):
    '''
    Delete a layer
    '''
    if naruto_layer.has_children:
        click.secho(
            'WARNING: This layer has {} direct children and a further {} descendants.'.format(
                len(naruto_layer.children),
                len(naruto_layer.descendants)),
            fg='red')

    if naruto_layer.mounted:
        click.confirm(
            '{} is currently mounted. Must unmount first. Continue?'.format(naruto_layer),
            abort=True)
        naruto_layer.unmount_all()

    click.confirm(
        click.style(
            'This will irreversible delete {} and all {} descendants. Continue?'.format(
                naruto_layer, len(naruto_layer.descendants)),
            fg='red'), abort=True)

    shutil.rmtree(str(naruto_layer.path.resolve()))


@cli.command()
@LAYER_OPT
@click.argument('description', default='')
def description(naruto_layer, description):
    '''
    Get set layer description
    '''
    if description:
        naruto_layer.description = description
    else:
        click.echo(naruto_layer.description)


@cli.command()
@LAYER_OPT
@click.argument('tags', nargs=-1)
def tags(naruto_layer, tags):
    '''
    Get set tags
    '''
    if tags:
        naruto_layer.tags = tags
    else:
        click.echo(', '.join(naruto_layer.tags))


@cli.command()
@LAYER_OPT
@click.argument('tags', nargs=-1)
def add_tags(naruto_layer, tags):
    ''' Add tag to layer'''
    naruto_layer.tags = naruto_layer.tags.union(tags)


@cli.command()
@LAYER_OPT
@click.argument('tags', nargs=-1)
def remove_tags(naruto_layer, tags):
    ''' Remove tag from layer'''
    naruto_layer.tags = naruto_layer.tags.difference(tags)
