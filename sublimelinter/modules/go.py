# encoding: utf-8
# golang.py - sublimelint package for checking golang files

import glob
import os
import re
import subprocess
from collections import namedtuple
from distutils.spawn import find_executable

from base_linter import BaseLinter, INPUT_METHOD_FILE

CONFIG = {
    'language': 'Go',
    'input_method': INPUT_METHOD_FILE,
}


GoError = namedtuple('GoError', 'line position type message')


def run(command):
    print 'Go linter running', ' '.join(command)
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    return out.splitlines() + err.splitlines()


def parse_lines(view, filename, pattern, lines):
    for line in lines:
        match = pattern.match(line)
        if match is not None and match.group(1).endswith(filename):
            yield match


class BaseGoLinter(object):
    binary = None
    pattern = None
    type = 'error'

    def run(self, view, filename):
        """Run linter, returning linter output. Each output line will be processed by apply()."""
        raise NotImplementedError

    @classmethod
    def valid(cls):
        cls.binary = find_executable(cls.binary)
        if cls.binary is not None:
            print 'GoLinter: %s enabled' % cls.__name__
        return cls.binary is not None

    def apply(self, view, filename, line):
        match = self.pattern.match(line)
        if match is None:
            return None
        # "go vet" returns a relative path which fails to match, and this
        # doesn't hurt the other implementations
        match_filename = os.path.abspath(match.group('filename'))
        if filename != match_filename:
            return None

        groups = match.groupdict()
        if 'position' in groups:
            position = int(groups['position'])
        else:
            position = None
        return GoError(line=int(groups['line_number']), position=position, type=self.type, message=groups['message'])


class GoCompileLinter(BaseGoLinter):
    binary = 'go'
    pattern = re.compile(r'(?P<filename>.*?):(?P<line_number>\d+): (?P<message>.*)')
    pkg_path = '{GOPATH}/pkg/{GOOS}_{GOARCH}'

    def __init__(self):
        self._env = self._go_env('go')

    def run(self, view, filename):
        return run(self._args(filename))

    def _args(self, filename):
        dir = os.path.dirname(filename)
        pkg_path = self.pkg_path.format(**self._env)
        # Find files in the current files package. Allows for split-package directories.
        file_package = self._package_for_file(filename)
        files = [file for file in glob.glob(dir + '/*.go')
                 if self._package_for_file(file) == file_package]
        cmd = [self.binary, 'tool', '6g', '-o', '/dev/null', '-D', dir, '-I', pkg_path] + files
        return cmd

    def _package_for_file(self, filename):
        with open(filename) as fd:
            for line in fd:
                if line.startswith('package'):
                    return line.split()[1]

    def _go_env(self, go):
        env = {}
        for line in run([go, 'env']):
            k, v = line.split('=')
            env[k] = v[1:-1].decode('string_escape')
        return env


class GolintLinter(BaseGoLinter):
    binary = 'golint'
    pattern = re.compile(r'(?P<filename>.*?):(?P<line_number>\d+):(?P<position>\d+): (?P<message>.*)')
    type = 'warning'

    def run(self, view, filename):
        return run([self.binary, filename])

    def apply(self, view, filename, line):
        error = super(GolintLinter, self).apply(view, filename, line)

        line_point = view.text_point(error.line - 1, 0)
        line_text = view.substr(view.line(line_point))
        if '-golint' in line_text:
            return None

        return error


class GoVetLinter(BaseGoLinter):
    binary = 'go'
    pattern = re.compile(r'(?P<filename>.*?):(?P<line_number>\d+): (?P<message>.*)')

    def run(self, view, filename):
        return run([self.binary, 'vet', filename])


class Linter(BaseLinter):
    linters = [GoCompileLinter, GolintLinter, GoVetLinter]

    def __init__(self, config):
        super(Linter, self).__init__(config)
        self.linters = [linter() for linter in Linter.linters if linter.valid()]

    def built_in_check(self, view, code, filename):
        errors = []
        for linter in self.linters:
            try:
                for line in linter.run(view, filename):
                    error = linter.apply(view, filename, line)
                    if error is not None:
                        errors.append(error)
            except Exception as e:
                print '%s: error: %s' % (linter.__class__.__name__, e)
        return errors

    def parse_errors(self, view, errors, lines, errorUnderlines,
                     violationUnderlines, warningUnderlines, errorMessages,
                     violationMessages, warningMessages):
        for error in errors:
            if error.type == 'error':
                underlines = errorUnderlines
                messages = errorMessages
            else:
                underlines = warningUnderlines
                messages = warningMessages
            if error.position is not None:
                self.underline_range(view, error.line, error.position - 1, underlines)
            self.add_message(error.line, lines, error.message, messages)
