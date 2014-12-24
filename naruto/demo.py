# -*- coding: utf-8 -*-
"""
Demo script
"""
import logging
import os.path
import pathlib
import tempfile

import click
from click import echo
import sh

from naruto.cli import DEFAULT_NARUTO_HOME


DEV_LOGGER = logging.getLogger(__name__)


def run_command_and_output(command):
    '''
    Run a command and format the output for a demo
    '''
    command_args = ' '.join(arg.decode() for arg in command._partial_baked_args)
    path = pathlib.Path(command._path).name
    click.secho('BASH>>> {} {}'.format(path, command_args), fg='green')
    result = command(_err_to_out=True)
    click.secho(str(result), fg='blue')
    return result


def naruto_cli(sub_command, *args, **kwargs):
    command = sh.naruto.bake(verbosity=logging.getLogger().getEffectiveLevel())
    if sub_command is None:
        command = sh.naruto.bake(*args, **kwargs)
    else:
        command = sh.naruto.bake(sub_command, *args, **kwargs)
    return run_command_and_output(command)


def bash(command, *args, **kwargs):
    command = sh.Command(command)
    command = command.bake(*args, **kwargs)
    return run_command_and_output(command)


@click.command()
@click.option(
    '--interactive/--not-interactive',
    help='Disable interactive functions for testing',
    default=True)
@click.option(
    '--verbosity',
    '-V',
    help='Set verbosity level explicitly (int or CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET)',
    default=logging.CRITICAL,
    type=str)
def demo(interactive, verbosity):
    '''
    This tool demos the ity of naruto.
    '''
    click.clear()

    try:
        verbosity = int(verbosity)
    except ValueError:
        #Ints and strings are ok
        pass
    logging.basicConfig(level=verbosity)
    DEV_LOGGER.debug('Set log level to %s', verbosity)

    if interactive:
        pause = click.pause

        click.confirm(
            'This will demo the functionality of naruto. '
            'It will require permissions to mount and will make a number of modifications '
            'in {}'.format(DEFAULT_NARUTO_HOME), abort=True)
    else:
        pause = click.echo

    echo(
        'Naruto is a wrapper around aufs that makes use of its layered filesystem to provide a'
        ' filesystem that can be easily snapshotted and branched without need to loads of copies')

    LAYER_NAME = 'my_new_layer'
    echo('First we create a new layer.')
    naruto_cli('create', LAYER_NAME)

    echo('This will have created a new directory in our home')
    bash('ls', os.path.expanduser('~/.naruto'))

    pause()

    echo('We can then mount this directory somewhere and make some modifications...')
    mount_dir_1 = tempfile.TemporaryDirectory(suffix='_mount_dir_1')

    naruto_cli('mount', mount_dir_1.name, layer=LAYER_NAME)

    mount_dir_1_path = pathlib.Path(mount_dir_1.name)
    text_file = (mount_dir_1_path / 'file_1.txt')
    text_file.open('w').write('Modification 1\n')

    bash('ls', str(mount_dir_1_path))
    bash('cat', str(text_file))

    pause()

    echo('Finally we can remove the layer and all its children')
    naruto_cli('delete', layer=LAYER_NAME, no_prompt=True)
