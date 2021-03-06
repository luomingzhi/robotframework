#!/usr/bin/env python

#  Copyright 2008-2015 Nokia Networks
#  Copyright 2016-     Robot Framework Foundation
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Module implementing the command line entry point for the `Tidy` tool.

This module can be executed from the command line using the following
approaches::

    python -m robot.tidy
    python path/to/robot/tidy.py

Instead of ``python`` it is possible to use also other Python interpreters.

This module also provides :class:`Tidy` class and :func:`tidy_cli` function
that can be used programmatically. Other code is for internal usage.
"""

import os
import sys

# Allows running as a script. __name__ check needed with multiprocessing:
# https://github.com/robotframework/robotframework/issues/1137
if 'robot' not in sys.modules and __name__ == '__main__':
    import pythonpathsetter

from robot.errors import DataError
from robot.parsing import Model
from robot.utils import Application, file_writer
# TODO: expose from package root
from robot.running.builder.suitestructure import (SuiteStructureBuilder,
                                                  SuiteStructureVisitor)
from robot.writer import DataFileWriter

# TODO: maybe rename --format to --extension
# Proofread usage
USAGE = """robot.tidy -- Robot Framework test data clean-up tool

Version:  <VERSION>

Usage:  python -m robot.tidy [options] inputfile
   or:  python -m robot.tidy [options] inputfile [outputfile]
   or:  python -m robot.tidy --inplace [options] inputfile [more input files]
   or:  python -m robot.tidy --recursive [options] directory

Tidy tool can be used to clean up and change format of Robot Framework test
data files. The output is written into the standard output stream by default,
but an optional output file can be given as well. Files can also be modified
in-place using --inplace or --recursive options.

Options
=======

 -i --inplace    Tidy given file(s) so that original file(s) are overwritten
                 (or removed, if the format is changed). When this option is
                 used, it is possible to give multiple input files.
                 Examples:
                   python -m robot.tidy --inplace tests.robot
                   python -m robot.tidy --inplace --format robot *.txt
 -r --recursive  Process given directory recursively. Files in the directory
                 are processed in-place similarly as when --inplace option
                 is used. Does not process referenced resource files.
 -f --format txt|robot
                 Output file format. If omitted, the format of the input
                 file is used.
 -p --usepipes   Use pipe ('|') as a cell separator in the plain text format.
 -s --spacecount number
                 The number of spaces between cells in the plain text format.
                 Default is 4.
 -l --lineseparator native|windows|unix
                 Line separator to use in outputs. The default is 'native'.
                 native:  use operating system's native line separators
                 windows: use Windows line separators (CRLF)
                 unix:    use Unix line separators (LF)
 -h -? --help    Show this help.

Cleaning up the test data
=========================

Test case files can be normalized using Tidy. Tidy always writes consistent
headers, consistent order for settings, and consistent amount of whitespace
between sections and cells.

Examples:
  python -m robot.tidy messed_up_tests.robot cleaned_up_tests.robot
  python -m robot.tidy --inplace tests.robot
  python -m robot.tidy --recursive path/to/tests

Changing the test data format
=============================

Robot Framework supports test data in various formats, but nowadays the
plain text format with the '.robot' extension is the most commonly used.
Tidy makes it easy to convert data from one format to another.

Input format is always determined based on the extension of the input file.
If output file is given, the output format is got from its extension, and
when using --inplace or --recursive, it is possible to specify the desired
format using the --format option.

Examples:
  python -m robot.tidy tests.txt tests.robot
  python -m robot.tidy --inplace tests.robot
  python -m robot.tidy --format robot --recursive path/to/tests

Output encoding
===============

All output files are written using UTF-8 encoding. Outputs written to the
console use the current console encoding.

Alternative execution
=====================

In the above examples Tidy is used only with Python, but it works also with
Jython and IronPython. Above it is executed as an installed module, but it
can also be run as a script like `python path/robot/tidy.py`.

For more information about Tidy and other built-in tools, see
http://robotframework.org/robotframework/#built-in-tools.
"""


class Tidy(SuiteStructureVisitor):
    """Programmatic API for the `Tidy` tool.

    Arguments accepted when creating an instance have same semantics as
    Tidy command line options with same names.
    """

    def __init__(self, format='robot', use_pipes=False, space_count=4,
                 line_separator=os.linesep):
        self._options = dict(format=format, pipe_separated=use_pipes,
                             txt_separating_spaces=space_count,
                             line_separator=line_separator)

    def file(self, path, outpath=None):
        """Tidy a file.

        :param path: Path of the input file.
        :param outpath: Path of the output file. If not given, output is
            returned.

        Use :func:`inplace` to tidy files in-place.
        """
        data = Model(path)
        with self._get_writer(outpath) as writer:
            self._save_file(data, writer)
            if not outpath:
                return writer.getvalue().replace('\r\n', '\n')

    def _get_writer(self, outpath):
        return file_writer(outpath, newline=self._options['line_separator'],
                           usage='Tidy output')

    def inplace(self, *paths):
        """Tidy file(s) in-place.

        :param paths: Paths of the files to to process.
        """
        for path in paths:
            data = Model(path)
            os.remove(path)
            self._save_file(data, output=self._get_writer(path))

    def directory(self, path):
        """Tidy a directory.

        :param path: Path of the directory to process.

        All files in a directory, recursively, are processed in-place.
        """
        data = SuiteStructureBuilder().build([path])
        data.visit(self)

    def _save_file(self, data, output=None):
        DataFileWriter(output=output, **self._options).write(data)

    def visit_file(self, file):
        self.inplace(file.source)

    def visit_directory(self, directory):
        if directory.init_file:
            self.inplace(directory.init_file)
        for child in directory.children:
            child.visit(self)


class TidyCommandLine(Application):
    """Command line interface for the `Tidy` tool.

    Typically :func:`tidy_cli` is a better suited for command line style
    usage and :class:`Tidy` for other programmatic usage.
    """

    def __init__(self):
        Application.__init__(self, USAGE, arg_limits=(1,))

    def main(self, arguments, recursive=False, inplace=False, format='txt',
             usepipes=False, spacecount=4, lineseparator=os.linesep):
        tidy = Tidy(format=format, use_pipes=usepipes, space_count=spacecount,
                    line_separator=lineseparator)
        if recursive:
            tidy.directory(arguments[0])
        elif inplace:
            tidy.inplace(*arguments)
        else:
            output = tidy.file(*arguments)
            self.console(output)

    def validate(self, opts, args):
        validator = ArgumentValidator()
        opts['recursive'], opts['inplace'] = validator.mode_and_args(args,
                                                                     **opts)
        opts['format'] = validator.format(args, **opts)
        opts['lineseparator'] = validator.line_sep(**opts)
        if not opts['spacecount']:
            opts.pop('spacecount')
        else:
            opts['spacecount'] = validator.spacecount(opts['spacecount'])
        return opts, args


class ArgumentValidator(object):

    def mode_and_args(self, args, recursive, inplace, **others):
        recursive, inplace = bool(recursive), bool(inplace)
        validators = {(True, True): self._recursive_and_inplace_together,
                      (True, False): self._recursive_mode_arguments,
                      (False, True): self._inplace_mode_arguments,
                      (False, False): self._default_mode_arguments}
        validator = validators[(recursive, inplace)]
        validator(args)
        return recursive, inplace

    def _recursive_and_inplace_together(self, args):
        raise DataError('--recursive and --inplace can not be used together.')

    def _recursive_mode_arguments(self, args):
        if len(args) != 1:
            raise DataError('--recursive requires exactly one argument.')
        if not os.path.isdir(args[0]):
            raise DataError('--recursive requires input to be a directory.')

    def _inplace_mode_arguments(self, args):
        if not all(os.path.isfile(path) for path in args):
            raise DataError('--inplace requires inputs to be files.')

    def _default_mode_arguments(self, args):
        if len(args) not in (1, 2):
            raise DataError('Default mode requires 1 or 2 arguments.')
        if not os.path.isfile(args[0]):
            raise DataError('Default mode requires input to be a file.')

    def format(self, args, format, inplace, recursive, **others):
        if not format:
            if inplace or recursive or len(args) < 2:
                return None
            format = os.path.splitext(args[1])[1][1:]
        format = format.upper()
        if format not in ('TXT', 'ROBOT'):
            raise DataError("Invalid format '%s'." % format)
        return format

    def line_sep(self, lineseparator, **others):
        values = {'native': os.linesep, 'windows': '\r\n', 'unix': '\n'}
        try:
            return values[(lineseparator or 'native').lower()]
        except KeyError:
            raise DataError("Invalid line separator '%s'." % lineseparator)

    def spacecount(self, spacecount):
        try:
            spacecount = int(spacecount)
            if spacecount < 2:
                raise ValueError
        except ValueError:
            raise DataError('--spacecount must be an integer greater than 1.')
        return spacecount


def tidy_cli(arguments):
    """Executes `Tidy` similarly as from the command line.

    :param arguments: Command line arguments as a list of strings.

    Example::

        from robot.tidy import tidy_cli

        tidy_cli(['--format', 'robot', 'tests.txt'])
    """
    TidyCommandLine().execute_cli(arguments)


if __name__ == '__main__':
    tidy_cli(sys.argv[1:])
