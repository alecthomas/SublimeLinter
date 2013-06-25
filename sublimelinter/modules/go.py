# encoding: utf-8
# golang.py - sublimelint package for checking golang files

import glob
import os
import re
import subprocess

from base_linter import BaseLinter, INPUT_METHOD_FILE

CONFIG = {
    'language': 'Go',
    'input_method': INPUT_METHOD_FILE,
}


class Linter(BaseLinter):
    pkg_path = '{GOPATH}/pkg/{GOOS}_{GOARCH}'

    def get_executable(self, view):
        try:
            path = self.get_mapped_executable(view, 'go')
            self.env = self._go_env(path)
            return (True, path, 'using "{0}"'.format(path))
        except Exception, e:
            return (False, '', 'go is required: {0}'.format(e))

    def get_lint_args(self, view, code, filename):
        self.filename = filename
        dir = os.path.dirname(filename)
        pkg_path = self.pkg_path.format(**self.env)
        # Find files in the current files package. Allows for split-package directories.
        file_package = self._package_for_file(filename)
        files = [file for file in glob.glob(dir + '/*.go')
                 if self._package_for_file(file) == file_package]
        cmd = ['tool', '6g', '-o', '/dev/null', '-D', dir, '-I', pkg_path] + files
        print ' '.join(cmd)
        return cmd

    def parse_errors(self, view, errors, lines, errorUnderlines,
                     violationUnderlines, warningUnderlines, errorMessages,
                     violationMessages, warningMessages):
        for line in errors.splitlines():
            match = re.match(r'(.*?):(.*?):(.*)', line)
            if match and self.filename.endswith(match.group(1)):
                line, error = match.group(2), match.group(3)
                print match.groups()
                self.add_message(int(line), lines, error, errorMessages)

    def _go_env(self, go):
        p = subprocess.Popen([go, 'env'], stdout=subprocess.PIPE)
        out, _ = p.communicate()
        env = {}
        for line in out.splitlines():
            k, v = line.split('=')
            env[k] = v[1:-1].decode('string_escape')
        print env
        return env

    def _package_for_file(self, filename):
        with open(filename) as fd:
            for line in fd:
                if line.startswith('package'):
                    return line.split()[1]
