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

import collections
import os

import six

root = '/'
sep = '/'
curdir = '.'
pardir = '..'


class FSPath(tuple):
    """
    Represent an ``FSTree`` path.
    """

    def __new__(cls, path, relative=None, parents=0, absolute=False):
        """
        Create an ``FSPath`` instance.

        :param path: The path string or a list of path elements.  If a
                     list, the ``absolute`` and ``parents`` attributes
                     will be set from the corresponding keyword
                     arguments, and the path will not be normalized.
        :param relative: The absolute ``FSPath`` instance this path
                         should be interpreted as relative to.  If not
                         given, the path will be a relative path.
        :param parents: An integer value indicating the number of
                        parent directory references included in the
                        path.  Only used if ``path`` is not a string.
        :param absolute: A boolean value indicating whether the path
                         is an absolute path.  Only used if ``path``
                         is not a string.

        :returns: An initialized ``FSPath`` instance.
        """

        # If the path is not a string, we need do no parsing
        if not isinstance(path, six.string_types):
            obj = super(FSPath, cls).__new__(cls, path)
            obj._absolute = absolute
            obj._parents = parents
            return obj

        # Is the path absolute?  If not, what's it relative to?
        if path.startswith(root) or relative is None:
            absolute = path.startswith(root)
            path_elems = []
        else:
            absolute = True
            path_elems = list(relative)

        # Now, normalize the path
        parents = 0
        for elem in path.split(sep):
            # Skip empty elements
            if not elem or elem == curdir:
                continue

            # Pop-up parent elements
            if elem == pardir:
                if absolute or (path_elems and path_elems[-1] != pardir):
                    # Try to pop one element off
                    try:
                        path_elems.pop()
                    except IndexError:
                        pass
                else:
                    # Append a parent element
                    path_elems.append(pardir)
                    parents += 1

                continue

            # Add the element
            path_elems.append(elem)

        # Now, initialize the path
        obj = super(FSPath, cls).__new__(cls, path_elems)
        obj._absolute = absolute
        obj._parents = parents

        return obj

    def __str__(self):
        """
        Return the string form of the path.
        """

        # Special-case the empty path
        if not self._absolute and not self:
            return curdir

        return (root if self._absolute else '') + sep.join(self)

    def __repr__(self):
        """
        Return a representation of the path.
        """

        # Put together identifying information
        ident = []
        extra = ''
        if self._absolute:
            ident.append('absolute')
        if self._parents:
            ident.append('parent elements: %d' % self._parents)
        if ident:
            extra = ' (%s)' % ', '.join(ident)

        return ('<%s.%s object for "%s"%s at %#x>' %
                (self.__class__.__module__, self.__class__.__name__,
                 self, extra, id(self)))

    def __hash__(self):
        """
        Return a hash value for this path.
        """

        return hash((self._absolute, self[:]))

    def __eq__(self, other):
        """
        Determine whether this path equals another.

        :param other: The other path to compare to.

        :returns: A ``True`` value if the other path equals this path,
                  ``False`` otherwise.
        """

        # Convert the other to an FSPath
        if not isinstance(other, FSPath):
            other = FSPath(other)

        return (self._absolute, self[:]) == (other._absolute, other[:])

    def __ne__(self, other):
        """
        Determine whether this path does not equal another.

        :param other: The other path to compare to.

        :returns: A ``True`` value if the other path does not equal
                  this path, ``False`` otherwise.
        """

        # Convert the other to an FSPath
        if not isinstance(other, FSPath):
            other = FSPath(other)

        return (self._absolute, self[:]) != (other._absolute, other[:])

    def relative(self, start):
        """
        Compute the relative path from a given starting location to
        this one.  If both paths are relative, they are assumed to be
        relative to the same starting location.

        :param start: A path, specified as either a string or an
                      ``FSPath`` instance, from which to compute the
                      relative path to this path.

        :returns: An ``FSPath`` instance representing the relative
                  path from ``start`` to this path.
        """

        # Normalize start path
        if not isinstance(start, FSPath):
            start = FSPath(start)

        # Make sure paths match in absoluteness
        if (int(self._absolute) ^ int(start._absolute)) == 1:
            raise ValueError("one path absolute, one not")

        # Determine the common prefix
        i = len(os.path.commonprefix([self, start]))

        # Set up and return the relative path
        parents = len(start) - i
        return FSPath(((pardir,) * parents) + self[i:], parents=parents,
                      absolute=False)

    def absolute(self, relative):
        """
        Determine the absolute form of this path, given a starting
        point to interpret a relative path against.

        :param relative: An absolute ``FSPath`` instance this path
                         should be interpreted as relative to.

        :returns: An absolute path.
        """

        # If we're already absolute, nothing else to do
        if self._absolute:
            return self

        # Sanity-check the relative path
        if not isinstance(relative, FSPath):
            relative = FSPath(relative)
        if not relative._absolute:
            raise ValueError("relative parameter must be absolute path")

        # Normalize the path
        if self._parents:
            relative = relative[:-self._parents]
        return FSPath(relative + self[self._parents:], parents=0,
                      absolute=True)

    def get_system_path(self, fs_root):
        """
        Compute the system path given the file system root.

        :param fs_root: The file system root.

        :returns: The system path corresponding to this ``FSTree``
                  path.
        """

        if self._absolute:
            # It's an absolute path, so append to the file system root
            return os.path.join(fs_root, *self)

        # We're a relative path, so just use the system path separator
        return os.path.join(*self)

    def split_system_path(self, path):
        """
        If this path is a relative path consisting of only parent
        elements or only child elements, splits a given system path
        into the referenced element and the child directories elided.

        :param path: The system path to split.

        :returns: A tuple of the referenced path and the child path,
                  as strings.
        """

        # Normalize the path
        path = os.path.normpath(path)

        # Only works with relative paths of only parent elements or
        # only child elements
        if self._absolute:
            raise ValueError("cannot split with an absolute path")
        if self._parents and len(self) > self._parents:
            raise ValueError("cannot split with this path")

        # If we have only child elements, the split is easy
        if not self._parents:
            return (path, os.path.join(*self) if self else os.curdir)

        # OK, compute the parent...
        parent = os.path.normpath(os.path.join(path, *self))

        # Now, compute the elided child directories and return the
        # data
        return (parent, path[len(parent) + len(os.sep):])

    @property
    def is_absolute(self):
        """
        Determine whether the path is absolute.
        """

        return self._absolute

    @property
    def parents(self):
        """
        Retrieve the portion of the path which traverses the parents.
        """

        return sep.join(self[:self._parents])

    @property
    def remainder(self):
        """
        Retrieve the remainder, that is, the part of the path beyond
        the parents.
        """

        return sep.join(self[self._parents:])

    @property
    def non_absolute(self):
        """
        Retrieve a non-absolute version of this path.
        """

        if self._absolute:
            # Just return the path with absolute=False
            return FSPath(self, absolute=False, parents=0)

        # We're already relative, no need to create a new one
        return self
