# Copyright 2014 Kevin L. Mitchell
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import contextlib
import hashlib
import os

import six


# The size of blocks to read from a file while computing the digest of
# that file.
BLOCKSIZE = 64 * 1024

# The default hash algorithm to use.
DEFAULT_HASHER = 'md5'

# A value indicating that the parameter was not given
unset = object()


def deroot(path, root='/'):
    """
    Recomputes the given path with respect to the designated root.

    :param path: The absolute, normalized path to deroot.
    :param root: The root directory.  If ``path`` is not a descendant
                 of the root, a ``ValueError`` will be raised.
                 Defaults to "/".

    :returns: The absolute path relative to the designated root.
    """

    # Check if path is within the designated root
    if root != '/':
        if (len(path) < len(root) or path[:len(root)] != root or
                (len(path) > len(root) and path[len(root)] != '/')):
            raise ValueError("path '%s' outside of root '%s'" %
                             (path, root))

        # Trim off the root
        path = path[len(root):]
        if not path:
            path = '/'

    return path


def abspath(path, cwd=None, root='/'):
    """
    Calculate the absolute version of the designated path.  If the
    designated path is not absolute, it is interpreted relative to the
    current working directory, as constrained by the designated root.

    :param path: The path to convert to absolute form.
    :param cwd: The value to use as the current working directory.  If
                not given, ``os.getcwd()`` will be used.
    :param root: The root directory for interpreting the current
                 working directory.  If the current working directory
                 is not a descendent of the root, a ``ValueError``
                 will be raised.  Defaults to "/".

    :returns: The normalized absolute path.
    """

    # Use the canonical abspath on the root
    root = os.path.abspath(root)

    # Need to expand the path
    if not os.path.isabs(path):
        if cwd is None:
            if six.PY2 and isinstance(path, unicode):
                cwd = deroot(os.getcwdu(), root)  # pragma: no cover
            else:
                cwd = deroot(os.getcwd(), root)

        path = os.path.join(cwd, path)

    # Normalize the full path
    return os.path.normpath(path)


class RelPath(object):
    """
    A variant of the ``os.path.relpath()`` function.  The two paths
    are decomposed and two attributes are set: ``parents`` contains
    the number of parent levels, and ``remainder`` contains the path
    after the parent levels.  Conversion to a string yields the final
    relative path.
    """

    def __init__(self, path, start=os.curdir, root='/'):
        """
        Initialize a ``RelPath`` object.

        :param path: The path.
        :param start: The starting point from which to calculate the
                      relative path.  Defaults to the current
                      directory.
        :param root: The filesystem root against which the paths
                     should be interpreted.  If either of the paths is
                     not a descendent of the root, a ``ValueError``
                     will be raised.
        """

        if not path:
            raise ValueError("no path specified")

        # Convert the paths into absolute paths
        path = abspath(path, root)
        start = abspath(start, root)

        # Now let's split up the paths, omitting empty components
        self.path_list = [e for e in path.split(os.sep) if e]
        start_list = [e for e in start.split(os.sep) if e]

        # Determine the common prefix and the remaining elements
        i = len(os.path.commonprefix([self.path_list, start_list]))
        remainder = self.path_list[i:]

        # Store the parent length and the remainder
        self.parents = len(start_list) - i
        self.remainder = (os.path.join(*remainder) if remainder else '')

    def __str__(self):
        """
        Return the string form of the relative path.

        :returns: The final relative path.
        """

        # If they were the same path, return .
        if not self.parents and not self.remainder:
            return os.curdir

        # OK, compute the parents
        elems = [os.pardir] * self.parents
        if self.remainder:
            elems.append(self.remainder)
        return os.path.join(*elems)


@contextlib.contextmanager
def workdir(path):
    """
    A context manager allowing work to be done with the current
    working directory temporarily set to the designated path.  When
    used in a "with" statement with a variable, the variable will be
    bound to the name of the working directory upon entry to the
    context manager.

    :param path: The temporary working directory.
    """

    # Get the current working directory
    cwd = os.getcwd()

    # Switch to the desired working directory
    os.chdir(path)

    try:
        # Do the work; the variable of the 'with' will be the current
        # working directory
        yield cwd
    finally:
        # Restore to the original working directory
        os.chdir(cwd)


def get_hasher(algorithm):
    """
    A simple utility routine to return the hasher for a given
    algorithm.  A hasher is simply a callable that, when called with
    no arguments, will return an object which can be used for
    computing a hash digest.  See the documentation for the
    ``hashlib`` module for more information.

    :param algorithm: The algorithm to get a hasher for.  Must be one
                      of the attributes of the ``hashlib`` module.

    :returns: The desired hasher.
    """

    return getattr(hashlib, algorithm)


def digest(fo, digesters):
    """
    A simple utility to read data from a file object and digest it.

    :param fo: The file object to read data from.
    :param digesters: A sequence of digesters.  Each digester is the
                      result of calling the callable returned by
                      ``get_hasher()``.

    :returns: For convenience, returns the hex digest of the first
              digester in ``digesters``.
    """

    while True:
        # Read the file a block at a time
        buf = fo.read(BLOCKSIZE)
        if len(buf) == 0:
            # Hit end of file
            break

        # Update each digester
        for digester in digesters:
            digester.update(buf)

    # A convenience return
    return digesters[0].hexdigest()


def apply_ignore(ignore, dirpath, dirnames, filenames):
    """
    A utility function to apply a file ignore filter to a tuple
    yielded by ``os.walk()``.

    :param ignore: A callable to compute the files and directories to
                   ignore.  It is called with the ``dirpath`` and a
                   list of all entries in the directory, and must
                   return a sequence of all entries to ignore.  If it
                   is ``None``, the function does nothing.
    :param dirpath: The path to the directory containing the directory
                    and file names.
    :param dirnames: A list of directory names.  Will be modified in
                     place to exclude the ignored entries.
    :param filenames: A list of file names.  Will be modified in place
                      to exclude the ignored entries.
    """

    # If there's no ignore function, there's nothing for us to do
    if not ignore:
        return

    # Determine what's to be ignored
    ignored = set(ignore(dirpath, dirnames + filenames))

    # Recompute dirnames and filenames
    dirnames[:] = [d for d in dirnames if d not in ignored]
    filenames[:] = [f for f in filenames if f not in ignored]
