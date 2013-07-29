# encoding: utf-8
# golang.py - sublimelint package for checking golang files

import glob
import os
import re
import subprocess
from collections import namedtuple

from base_linter import BaseLinter, INPUT_METHOD_FILE

CONFIG = {
    'language': 'Go',
    'input_method': INPUT_METHOD_FILE,
}


GoError = namedtuple('GoError', 'line position type message')


def run(command):
    p = subprocess.Popen(command, stdout=subprocess.PIPE)
    out, _ = p.communicate()
    return out.splitlines()


def parse_lines(view, filename, pattern, lines):
    for line in lines:
        match = pattern.match(line)
        if match is not None and match.group(1).endswith(filename):
            yield match


class Linter(BaseLinter):
    pkg_path = '{GOPATH}/pkg/{GOOS}_{GOARCH}'
    go_6g_pattern = re.compile(r'(.*?):(\d+): (.*)')
    golint_pattern = re.compile(r'(.*?):(\d+):(\d+): (.*)')

    def __init__(self, config):
        super(Linter, self).__init__(config)
        self._linters = [self.golint_check, self.go_6g_check]
        self._env = self._go_env('go')

    def golint_check(self, view, filename):
        errors = []
        lines = run(['golint', filename])
        for match in parse_lines(view, filename, self.golint_pattern, lines):
            _, line_number, position, message = match.groups()
            line_number = int(line_number)
            line_point = view.text_point(line_number - 1, 0)
            line_text = view.substr(view.line(line_point))
            if '-golint' in line_text:
                continue
            errors.append(GoError(line=line_number, position=int(position), type='warning', message=message))
        return errors

    def go_6g_check(self, view, filename):
        errors = []
        lines = run(self._get_go_6g_args(filename))
        for match in parse_lines(view, filename, self.go_6g_pattern, lines):
            _, line_number, message = match.groups()
            errors.append(GoError(line=int(line_number), position=None, type='error', message=message))
        return errors

    def _get_go_6g_args(self, filename):
        dir = os.path.dirname(filename)
        pkg_path = self.pkg_path.format(**self._env)
        # Find files in the current files package. Allows for split-package directories.
        file_package = self._package_for_file(filename)
        files = [file for file in glob.glob(dir + '/*.go')
                 if self._package_for_file(file) == file_package]
        cmd = ['go', 'tool', '6g', '-o', '/dev/null', '-D', dir, '-I', pkg_path] + files
        print ' '.join(cmd)
        return cmd

    def built_in_check(self, view, code, filename):
        errors = []
        for linter in self._linters:
            try:
                errors.extend(linter(view, filename))
            except Exception as e:
                print 'GoLinter: error: %s' % e
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
                self.underline_word(view, error.line, error.position - 1, underlines)
            self.add_message(error.line, lines, error.message, messages)

    def _go_env(self, go):
        env = {}
        for line in run([go, 'env']):
            k, v = line.split('=')
            env[k] = v[1:-1].decode('string_escape')
        return env

    def _package_for_file(self, filename):
        with open(filename) as fd:
            for line in fd:
                if line.startswith('package'):
                    return line.split()[1]
