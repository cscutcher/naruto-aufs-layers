# -*- coding: utf-8 -*-
"""
Main group for naruto cli
"""
import io
import logging
import os
import pathlib
import shutil

import click

from naruto import NarutoLayer, LayerNotFound

DEV_LOGGER = logging.getLogger(__name__)
DEFAULT_NARUTO_HOME = pathlib.Path(os.path.expanduser('~/.naruto'))
DEFAULT_LOG_LEVEL = logging.INFO


class CLIContext(object):
    '''
    Context for CLI
    '''
    def __init__(self):
        self.naruto_home = DEFAULT_NARUTO_HOME


cli_context = click.make_pass_decorator(CLIContext, ensure=True)


@click.group()
@click.option(
    '--naruto-home',
    default=str(DEFAULT_NARUTO_HOME),
    type=click.Path(
        file_okay=False,
        dir_okay=True,
        writable=True,
        readable=True,
        resolve_path=True,
        exists=False),
    help=(
        'Set default config directory used to store and retrieve layers. Default: {}'.format(
            DEFAULT_NARUTO_HOME)))
@click.option(
    '--verbosity',
    '-V',
    help='Set verbosity level explicitly (int or CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET)',
    default=DEFAULT_LOG_LEVEL,
    type=str)
@cli_context
def naruto_cli(ctx, naruto_home, verbosity):
    '''
    CLI for naruto
    '''
    try:
        verbosity = int(verbosity)
    except ValueError:
        #Ints and strings are ok
        pass
    logging.basicConfig(level=verbosity)
    DEV_LOGGER.debug('Set log level to %s', verbosity)

    ctx.naruto_home = pathlib.Path(naruto_home)
    DEV_LOGGER.debug('Home path is %r', ctx.naruto_home)


class _LayerLookup(click.ParamType):
    '''
    Type which loads naruto dir
    '''
    name = 'NarutoDir'

    def __init__(self, allow_discovery=True):
        self._allow_discovery = allow_discovery

    def convert(self, value, param, local_context):
        '''
        Parse Naruto argument
        '''
        DEV_LOGGER.debug('Trying to find root layer for value %r', value)
        root_spec, _, layer_spec = value.partition(':')
        cli_context = local_context.ensure_object(CLIContext)

        if not root_spec and self._allow_discovery:
            try:
                layer = NarutoLayer.find_layer_mounted_at_dest(pathlib.Path(os.getcwd()))
            except LayerNotFound:
                self.fail(
                    'Couldn\'t auto-discover layer. '
                    'You must in a directory which is a mounted layer for auto-discovery to work')
        else:
            if os.sep in root_spec:
                naruto_root = pathlib.Path(root_spec)
            else:
                naruto_root = cli_context.naruto_home / root_spec

            try:
                naruto_root, = tuple(naruto_root.iterdir())
            except FileNotFoundError:
                self.fail('Directory {} does not exist'.format(naruto_root))
            except ValueError:
                self.fail('Unexpected number of folders in {}'.format(naruto_root))

            try:
                layer = NarutoLayer(naruto_root)
            except LayerNotFound:
                self.fail('{!s} is not a layer.'.format(naruto_root))

        if layer_spec:
            layer = layer.find_layer(layer_spec)

        DEV_LOGGER.debug('Parsed layer at %r from cli', layer)
        return layer


@naruto_cli.command()
@click.argument('name_or_path')
@click.option('--description', help='Add description to new naruto layer')
@cli_context
def create(ctx, name_or_path, description):
    '''
    Create new NarutoLayer
    '''
    if os.sep in name_or_path:
        path = pathlib.Path(name_or_path)
        DEV_LOGGER.info('Creating at raw path %r', path)
    else:
        home_naruto_dir = ctx.naruto_home
        if not home_naruto_dir.is_dir():
            home_naruto_dir.mkdir()
        home_naruto_dir = home_naruto_dir.resolve()

        path = home_naruto_dir / name_or_path
        if not path.is_dir():
            path.mkdir()

        # Check nothing nasty from user
        assert path.parent == home_naruto_dir

        DEV_LOGGER.info('Creating %r in naruto home %r', home_naruto_dir, name_or_path)

        if len(tuple(path.iterdir())) != 0:
            raise Exception('Expected create directory {!s} to be empty'.format(path))

    NarutoLayer.create(path, description=description)


@naruto_cli.command()
@cli_context
def list_home_layers(ctx):
    '''
    List layers stored in home directory
    '''
    for path in ctx.naruto_home.iterdir():
        click.echo(str(path))


#################################################################################################
## Commands that modify or inspect existing layers
#################################################################################################
def _modification_command(fn):
    '''
    Add common options for modification
    '''
    fn = naruto_cli.command()(fn)
    layer_lookup_help = (
        'This specifies the layer you want to act upon. '
        'If not specified we will try and discover the layer you have currently mounted.')

    fn = click.option('-l', '--layer', type=_LayerLookup(), default='', help=layer_lookup_help)(fn)
    return fn


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


@_modification_command
def info(layer):
    '''
    Get info about a layer
    '''
    io_stream = io.StringIO()
    InfoNodeAdapter(layer.get_root()).output(io_stream, 0, highlight=(layer,))
    click.echo(io_stream.getvalue())


@_modification_command
@click.argument('mount_dest')
def mount(layer, mount_dest):
    '''
    Mount a layer
    '''
    layer.mount(mount_dest)


@_modification_command
@click.argument('mount_dest')
@click.option('--description', help='Add description to new naruto layer')
def branch_and_mount(layer, mount_dest, description):
    '''
    Branch a layer and mount at new dest
    '''
    layer.create_child(description=description).mount(mount_dest)


@_modification_command
def unmount_all(layer):
    '''
    Unmount all uses of this layer
    '''
    layer.unmount_all()


@_modification_command
def find_mounts(layer):
    '''
    Find where layer is mounted
    '''
    for branch in layer.find_mounted_branches_iter():
        click.echo('{branch.path}={branch.permission} at {branch.mount_point}'.format(
            branch=branch))


@_modification_command
def delete(layer):
    '''
    Delete a layer
    '''
    if layer.has_children:
        click.secho(
            'WARNING: This layer has {} direct children and a further {} descendants.'.format(
                len(layer.children),
                len(layer.descendants)),
            fg='red')

    if layer.mounted:
        click.confirm(
            '{} is currently mounted. Must unmount first. Continue?'.format(layer),
            abort=True)
        layer.unmount_all()

    click.confirm(
        click.style(
            'This will irreversible delete {} and all {} descendants. Continue?'.format(
                layer, len(layer.descendants)),
            fg='red'), abort=True)

    shutil.rmtree(str(layer.path.resolve()))


@_modification_command
@click.argument('description', default='')
def description(layer, description):
    '''
    Get set layer description
    '''
    if description:
        layer.description = description
    else:
        click.echo(layer.description)


@_modification_command
@click.argument('tags', nargs=-1)
def tags(layer, tags):
    '''
    Get set tags
    '''
    if tags:
        layer.tags = tags
    else:
        click.echo(', '.join(layer.tags))


@_modification_command
@click.argument('tags', nargs=-1)
def add_tags(layer, tags):
    ''' Add tag to layer'''
    layer.tags = layer.tags.union(tags)


@_modification_command
@click.argument('tags', nargs=-1)
def remove_tags(layer, tags):
    ''' Remove tag from layer'''
    layer.tags = layer.tags.difference(tags)
