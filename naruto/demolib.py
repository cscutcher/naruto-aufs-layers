# -*- coding: utf-8 -*-
"""
Library for doing quick semi-automated demo's of functionality
"""
import logging
import subprocess
import click
import ipdb

DEV_LOGGER = logging.getLogger(__name__)


class DemoContext(object):
    '''
    Object for controlling demo
    '''
    def __init__(self, interactive=True, silent=False):
        self._interactive = interactive
        self._silent = silent

    def start(self):
        '''
        Start demo
        '''
        click.clear()

    def pause(self):
        '''
        Pause the demo and allow the user to drop to terminal and jazz
        '''
        if self._interactive and not self._silent:
            user_input = click.prompt(
                'Continue? [Press \'i\' to drop to ipdb] [y/n/i]',
                default='y',
                show_default=True,
                type=str).lower()
            if user_input == 'y':
                return
            elif user_input == 'i':
                ipdb.set_trace()
                return
            else:
                click.confirm(abort=True)
                return

    def confirm(self, message, abort=True):
        '''
        Confirm if user wants to continue
        '''
        if self._interactive and not self._silent:
            click.confirm(message, abort=abort)
        elif not self._silent:
            click.echo(message)

    def echo(self, message):
        '''
        Echo message in demo
        '''
        if not self._silent:
            click.echo(message)

    def _bash_ok_result(self, result):
        '''
        Output bash result if ok
        '''
        if not self._silent:
            click.secho(result)
            click.echo('\n')

    def _bash_fail_result(self, error_code, error_msg):
        '''
        Output a bash failure
        '''
        if not self._silent:
            click.secho(
                '[FAILED WITH {error_code}]\n{error_msg}'.format(
                    error_code=error_code, error_msg=error_msg),
                fg='red')
            click.echo('\n')

    def bash(self, command, *args, **kwargs):
        '''
        Run a bash command
        '''
        ok_codes = kwargs.pop('_ok_codes', ())
        expect_failure = kwargs.pop('_expect_failure', False)

        formatted_kwargs = tuple('--{} {}'.format(key, value) for key, value in kwargs.items())

        if len(args) > 0:
            command = ' '.join(str(arg) for arg in (command,) + args + formatted_kwargs)

        if not self._silent:
            click.secho('BASH> {}'.format(command), fg='green')

        try:
            result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as error:
            if error.returncode in ok_codes:
                self._bash_ok_result(error.output.decode('utf-8'))
                result = error.output
            else:
                self._bash_fail_result(error.returncode, error.output.decode('utf-8'))
                if not expect_failure:
                    raise
        else:
            self._bash_ok_result(result.decode('utf-8'))

        return result
