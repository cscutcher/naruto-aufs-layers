# -*- coding: utf-8 -*-
"""
I figured I'd see if I could semi semi-automate demos of this thing. It's still kinda ugly but
it'll do the job

The one advantage of doing it like this is I can run it with nosetests so I can be sure I've not
broken it.
"""
import logging
import os.path
import pathlib
import tempfile

import click

from naruto.cli import DEFAULT_NARUTO_HOME
from naruto.demolib import DemoContext


DEV_LOGGER = logging.getLogger(__name__)


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
def demo_cli(interactive, verbosity):
    '''
    This command is designed to do small semi-automated demos off naruto.

    TODO: Don't use users home for demo
    '''
    try:
        verbosity = int(verbosity)
    except ValueError:
        #Ints and strings are ok
        pass

    logging.basicConfig(level=verbosity)
    DEV_LOGGER.debug('Set log level to %s', verbosity)
    return demo(interactive, verbosity)


def demo(interactive, verbosity, silent=False):
    '''
    This command is designed to do small semi-automated demos off naruto.

    TODO: Don't use users home for demo
    '''

    demo = DemoContext(interactive=interactive, silent=silent)

    def naruto_cli(*args, **kwargs):
        demo.bash('naruto', '--verbosity {}'.format(verbosity), *args, **kwargs)

    demo.start()

    demo.confirm(
        'This will demo the functionality of naruto. '
        'It will require permissions to mount and will make a number of modifications '
        'in {}'.format(DEFAULT_NARUTO_HOME), abort=True)

    demo.echo(
        'Naruto is a wrapper around aufs that makes use of its layered filesystem to provide a'
        ' filesystem that can be easily snapshotted and branched without need to loads of copies')

    LAYER_NAME = 'my_new_layer'
    demo.echo('First we create a new layer.')

    naruto_cli('create', LAYER_NAME)

    demo.echo('This will have created a new directory in our home')
    demo.bash('ls', os.path.expanduser('~/.naruto'))

    demo.pause()

    demo.echo('We can then mount this directory somewhere and make some modifications...')
    mount_dir_1 = tempfile.TemporaryDirectory(suffix='_mount_dir_1')

    naruto_cli('mount', mount_dir_1.name, layer=LAYER_NAME)

    mount_dir_1_path = pathlib.Path(mount_dir_1.name)
    text_file_1_path = mount_dir_1_path / 'file_1.txt'

    demo.bash('echo \'{}\' > {}'.format('Modification 1', text_file_1_path))
    demo.bash('ls', str(mount_dir_1_path))
    demo.bash('cat', str(text_file_1_path))

    demo.pause()

    demo.echo('''
Now we can branch this to a new mount point.

We will be able to modify both the old and new mount point without affecting each other.

The time to create the new branch should be pretty instantaneous regardless of how many files\
are involved.''')

    mount_dir_2 = tempfile.TemporaryDirectory(suffix='_mount_dir_2')
    mount_dir_2_path = pathlib.Path(mount_dir_2.name)

    naruto_cli('branch_and_mount', mount_dir_2_path, layer=LAYER_NAME)

    text_file_1_path = mount_dir_2_path / 'file_1.txt'
    text_file_2_path = mount_dir_2_path / 'file_2.txt'
    demo.bash('echo \'{}\' > {}'.format('Modification 2', text_file_1_path))
    demo.bash('echo \'{}\' > {}'.format('Second file', text_file_2_path))
    demo.bash('ls', str(mount_dir_2_path))
    demo.bash('cat', str(text_file_1_path))

    demo.echo('These changes made in the second mount point aren\'t refleted back on the first')
    text_file_1_path = mount_dir_1_path / 'file_1.txt'
    demo.bash('ls', str(mount_dir_1_path))
    demo.bash('cat', str(text_file_1_path))
    demo.pause()

    demo.echo('We can display information about a mount point when we\'re inside it')
    demo.bash('cd {} ; naruto info'.format(mount_dir_1_path))
    demo.bash('cd {} ; naruto info'.format(mount_dir_2_path))

    demo.echo('Or we can use a query language to look at items')
    naruto_cli('info', layer='{}:root'.format(LAYER_NAME))
    naruto_cli('info', layer='{}:root^'.format(LAYER_NAME))
    naruto_cli('info', layer='{}:root^2'.format(LAYER_NAME))

    demo.pause()
    demo.echo('We can also update tags or change descriptions of layers')
    demo.bash('cd {} ; naruto description new_description'.format(mount_dir_1_path))
    demo.bash('cd {} ; naruto add_tags tag1'.format(mount_dir_1_path))
    demo.bash('cd {} ; naruto info'.format(mount_dir_1_path))

    demo.pause()
    demo.echo('Finally we can remove the layer and all its children')
    naruto_cli('delete', '--no-prompt', layer=LAYER_NAME)

    mount_dir_1.cleanup()
    mount_dir_2.cleanup()


def test_demo():
    '''
    Run demo for nosetests
    '''
    demo(verbosity=logging.getLogger().getEffectiveLevel(), interactive=False, silent=True)
