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

import os
import shutil
import stat
import sys
import tarfile
import weakref

import six

from fstree import cacheprop
from fstree import tarname
from fstree import utils


class FSEntry(object):
    """
    Represent a single entry in the file system tree.  Various
    operations can be performed using methods and item assignment, and
    various data collected via attribute access.
    """

    def __init__(self, root, name, path):
        """
        Initialize an ``FSEntry`` instance.

        :param tree: The ``FSTree`` instance that is the root of the
                     filesystem tree.
        :param name: The absolute name for this entry.
        :param path: The full system path for this entry.
        """

        self.tree = tree
        self.name = name
        self.path = path

        # The stat and lstat values are cached specially
        self._lstat = utils.unset
        self._stat = utils.unset

    def __getattr__(self, name):
        """
        Retrieve a dynamic attribute for the ``FSEntry`` instance.
        These are attributes with a leading prefix of ``st_`` or
        ``lst_``, which access the file stat entries from
        ``os.stat()`` or ``os.lstat()``, respectively.

        :param name: The name of the attribute.

        :returns: The value of the requested attribute.
        """

        if name.startswith('lst_'):
            # Result from os.lstat()
            return getattr(self.lstat, name[1:])
        elif name.startswith('st_'):
            # Result from os.stat()
            return getattr(self.stat, name)

        # Unrecognized attribute
        raise AttributeError("'%s' object has no attribute '%s'" %
                             (self.__class__.__name__, name))

    def __contains__(self, path):
        """
        Determine if a given file exists in the tree.

        :param path: The path to check the existence of.

        :returns: Returns a ``True`` value if the file exists,
                  ``False`` otherwise.
        """

        # If it's an FSEntry, check if it's in the correct tree
        if isinstance(path, FSEntry):
            return path.tree is self.tree and os.path.exists(path.path)

        # OK, it's just a regular string
        return os.path.exists(self._abs(path))

    def __getitem__(self, path):
        """
        Retrieve the ``FSEntry`` instance in this tree that describes
        the given ``path``.  A ``KeyError`` will be raised if the file
        doesn't exist, and a ``ValueError`` will be raised if ``path``
        is from a different tree.

        :param path: The path to find an ``FSEntry`` instance for.

        :returns: An instance of ``FSEntry``.
        """

        # Delegate to the tree's _get() method
        return self.tree._get(self._rel(path, False))

    def __setitem__(self, path, value):
        """
        Create or update a given file.  Assigning a string will copy
        the file or directory tree from the designated absolute path.
        For other behavior, use the ``Assignable`` subclasses.  A
        ``ValueError`` will be raised if ``path`` is from a different
        tree.

        :param path: The path to create or update.
        :param value: A string or ``Assignable`` instance that
                      designates how to update the path.
        """

        # Delegate to the tree's _set() method
        self.tree._set(self._rel(path, False), value)

    def __delitem__(self, path):
        """
        Delete a given file.  A ``ValueError`` will be raised if
        ``path`` is from a different tree.

        :param path: The path to delete.
        """

        # Delegate to the tree's _del() method
        self.tree._del(self._rel(path, False))

    def _abs(self, path):
        """
        A helper method to resolve a provided path relative to this
        filesystem entry.  Returns an absolute path against the
        underlying filesystem.

        :param path: The path to resolve.

        :returns: The resolved, absolute path.
        """

        # If it's an FSEntry, use the name
        if isinstance(path, FSEntry):
            path = path.name

        return self.tree._full(utils.abspath(path, cwd=self.name))

    def _paths(self, src, dst):
        """
        A helper method to resolve provided source and destination
        paths relative to this filesystem entry.

        :param src: The desired source file.
        :param dst: The desired destination.  If the destination is an
                    existing directory, the basename of the source
                    file will be appended to it.

        :returns: A tuple of the absolute source path, a relative
                  destination path, and an absolute destination path.
        """

        # Resolve the source, first
        if isinstance(src, FSEntry):
            # Use the full path when src is an FSEntry instance
            src = src.path
        else:
            # It's a file system path; interpret relative to our
            # location
            src = utils.abspath(src, cwd=self.path)

        # Now the destination...
        dst = self._rel(dst)
        full_dst = self.tree._full(dst)

        # If the destination is a directory, we need to add the source
        # basename
        if os.path.isdir(full_dst):
            basename = os.path.basename(src)
            dst = os.path.join(dst, basename)
            full_dst = os.path.join(full_dst, basename)

        return (src, dst, full_dst)

    def _rel(self, path, cross_tree=True):
        """
        A helper method to resolve a provided path relative to this
        filesystem entry.  Returns a relative path against the tree
        root.

        :param path: The path to resolve.
        :param cross_tree: If ``True`` (the default), allow
                           ``FSEntry`` instances that are in different
                           trees, using their name only.  If
                           ``False``, a ``ValueError`` will be raised.

        :returns: The desired tree-relative path.
        """

        # If it's an FSEntry, check if we're in the right tree
        if isinstance(path, FSEntry):
            if not cross_tree and path.tree is not self.tree:
                raise ValueError('path is not in this tree')

            # Grab the path name
            path = path.name

        # Resolve the path with the tree root as the root
        return utils.abspath(path, cwd=self.name)

    def access(self, mode):
        """
        Test whether the real uid and gid has access to the file under
        the given access mode.

        :param mode: The constant ``F_OK`` to test for existance, or
                     the bitwise OR of ``R_OK``, ``W_OK``, and
                     ``X_OK``.

        :returns: A ``True`` value if the real uid and gid have the
                  requested access, ``False`` otherwise.
        """

        return os.access(self.path, mode)

    def copy(self, src, dst=os.curdir, symlinks=False, ignore=None):
        """
        Copy a given source file.

        :param src: The filesystem path to the source file.  Can be an
                    ``FSEntry`` instance.
        :param dst: The destination for the copy operation.  If it is
                    a directory, the basename of the source file will
                    be added.
        :param symlinks: If ``True``, and if ``src`` is a directory,
                         symbolic links in the source tree result in
                         symbolic links in the destination tree.  If
                         ``False`` (the default), the contents of the
                         files pointed to by the symbolic links are
                         copied.
        :param ignore: An optional callable.  If ``src`` is a
                       directory, this callable will be called with a
                       directory name and a list of the file and
                       directory names in that directory; it should
                       return a list of file and directory names which
                       should be subsequently ignored.

        :returns: An ``FSEntry`` instance representing the copy of
                  ``src`` in its new location.
        """

        # Resolve the paths
        src, dst, full_dst = self._paths(src, dst)

        # Select the appropriate copy method
        if os.path.isdir(src):
            # Copy a directory
            shutil.copytree(src, full_dst, symlinks=symlinks, ignore=ignore)
        else:
            # Copy a file
            shutil.copy2(src, full_dst)

        # Return a reference to the new file
        return self.tree._get(dst)

    def digest(self, path=os.curdir, hasher=utils.DEFAULT_HASHER):
        """
        Compute the digest of the file.  Returns the hex digest of the
        file; to retrieve the digest in other forms, pass an explicit
        hasher or tuple of hashers.

        :param path: An optional path to a subelement of this
                     directory.
        :param hasher: The string name of the desired hash algorithm,
                       or a digester object as returned by one of the
                       hashers present in ``hashlib``, or a tuple of
                       such objects.  If not given, defaults to
                       ``utils.DEFAULT_HASHER``.

        :returns: The digest of the file, in hex.  If a tuple of
                  hashers was passed for ``hasher``, then the first
                  hasher will be returned.
        """

        # Set up the hasher, first
        if not hasher:
            raise ValueError('a hasher must be specified')
        elif isinstance(hasher, six.string_types):
            hasher = (utils.get_hasher(hasher)(),)
        elif not isinstance(hasher, tuple):
            hasher = (hasher,)

        # Open the desired file and digest it
        with self.open(path) as f:
            return utils.digest(f, hasher)

    def get(self, path, default=None):
        """
        Retrieve the ``FSEntry`` instance in this tree that describes
        the given ``path``.  If the file doesn't exist, a designated
        default value will be returned.

        :param path: The path to find an ``FSEntry`` instance for.
        :param default: A default value to return if the file does not
                        exist.

        :returns: An instance of ``FSEntry``, or the ``default``.
        """

        # Delegate to the tree's _get() method
        return self.tree._get(self._rel(path), default)

    def link(self, src, dst=os.curdir, ignore=None):
        """
        Create a hard link to a given file.

        :param src: The filesystem path to the source file.  Can be an
                    ``FSEntry`` instance.
        :param dst: The destination for the link operation.  If it is
                    a directory, the basename of the source file will
                    be added.
        :param ignore: An optional callable.  If ``src`` is a
                       directory, this callable will be called with a
                       directory name and a list of the file and
                       directory names in that directory; it should
                       return a list of file and directory names which
                       should be subsequently ignored.

        :returns: An ``FSEntry`` instance representing the hard link
                  ``dst``.
        """

        # Resolve the paths
        src, dst, full_dst = self._paths(src, dst)

        # You can make hard links of symlinks, so if source is a link
        # or not a directory, we want to go with the simple case
        if os.path.islink(src) or not os.path.isdir(src):
            # Create the hard link
            os.link(src, full_dst)
        else:
            # We can't hard link a directory, so make a tree of hard
            # links
            for srcpath, dirnames, filenames in os.walk(src):
                # Apply the ignore filter
                utils.apply_ignore(ignore, srcpath, dirnames, filenames)

                # Transplant srcpath on top of full_dst
                dstpath = full_dst + srcpath[len(src):]

                # Create the hard links
                for filename in filenames:
                    os.link(os.path.join(srcpath, filename),
                            os.path.join(dstpath, filename))

                # Create the subdirectories
                for dirname in dirnames:
                    os.makedirs(os.path.join(dstpath, dirname))

        # Return a reference to the hard link
        return self.tree._get(dst)

    def makedirs(self, path, mode=0o777):
        """
        Make the designated subdirectory.

        :param path: The name of the designated subdirectory.
                     Directory creation is recursive.  The name is
                     interpreted relative to this entry, and is rooted
                     at the tree.
        :param mode: The permissions to set on the directory.
                     Defaults to ``0o777``.

        :returns: An ``FSEntry`` instance representing the newly
                  created directory.
        """

        # Get the relative and full paths
        rel = self._rel(path)
        full = self.tree._full(rel)

        # Create the directory or directories...
        os.makedirs(full, mode)

        # Return a reference to the new directory
        return self.tree._get(rel)

    def move(self, src, dst):
        """
        Move a given file into the tree.

        :param src: The filesystem path to the source file.  Can be an
                    ``FSEntry`` instance.
        :param dst: The destination for the move operation.  If it is
                    a directory, the basename of the source file will
                    be added.

        :returns: An ``FSEntry`` instance representing the new
                  location of the file.
        """

        # Resolve the paths
        src, dst, full_dst = self._paths(src, dst)

        # Move the path
        shutil.move(src, full_dst)

        # Return a reference to the new location
        return self.tree._get(dst)

    def open(self, path=os.curdir, mode='r', buffering=utils.unset):
        """
        Open the file with the given mode and buffering values.  These
        values are the same as for the standard python ``open()``
        builtin.

        :param path: An optional path to a subelement of this
                     directory.
        :param mode: The access mode.  Defaults to 'r'.
        :param buffering: A value controlling how the file will be
                          buffered.  A value of 0 means unbuffered,
                          while a value of 1 means line buffered.
                          Larger values specify the buffer size.

        :returns: An open file object.
        """

        # Set up the args to feed to the underlying open builtin
        args = [self._abs(path), mode]
        if buffering is not utils.unset:
            args.append(buffering)

        return open(*args)

    def relpath(self, start, absolute=False):
        """
        Compute the relative path from the designated start directory
        to this entry.

        :param start: The starting directory.  May be another
                      ``FSEntry`` or a string.  If this is another
                      ``FSEntry``, and ``absolute`` is ``False``, only
                      the tree-relative entry name will be used; if
                      ``absolute`` is ``True``, the starting point
                      will be the full path name of the other
                      ``FSEntry``.
        :param absolute: If ``True``, the starting point may be
                         outside the tree, and the relative path may
                         exit the tree in that case.  If ``False``
                         (the default), the starting point is
                         interpreted as being relative to the root of
                         the tree.

        :returns: The relative path from ``start`` to this entry.
        """

        # Which is our path for this computation?
        path = self.path if absolute else self.name

        # Figure out which value to use for start
        if isinstance(start, FSEntry):
            start = start.path if absolute else start.name
        else:
            # Interpret start relative to this directory
            start = utils.abspath(start, cwd=path)

        # OK, now compute the relative path
        rel_path = utils.RelPath(path, start)

        return str(rel_path)

    def remove(self, path, ignore_errors=False, onerror=None):
        """
        Remove a file or directory tree.

        :param path: The path to remove.
        :param ignore_errors: If ``True``, errors are ignored,
                              regardless of the value of ``onerror``.
                              Defaults to ``False``.
        :param onerror: An optional callable which, if
                        ``ignore_errors`` is ``False``, will be called
                        with three arguments: the function that was
                        called, the path the function was called with,
                        and the exception information (as returned by
                        ``sys.exc_info()``.  If not provided, and
                        ``ignore_errors`` is ``False``, an exception
                        will be raised.
        """

        # Find the full path of the target file
        path = self._abs(path)

        # Is it a directory?
        if os.path.isdir(path):
            # It's a directory...
            return shutil.rmtree(path, ignore_errors, onerror)
        else:
            # Try removing the file
            try:
                os.remove(path)
            except OSError:
                if ignore_errors:
                    # Errors are being ignored
                    return
                elif onerror is None:
                    # Re-raise the error
                    raise

                # Call the onerror function
                onerror(os.remove, path, sys.exc_info())

    def symlink(self, src, dst=os.curdir, outside=False):
        """
        Create a symlink to the designated source.

        :param src: The source file the symlink should point to.  If
                    ``outside`` is ``False``, the symlink must point
                    inside the tree, or a ``ValueError`` will be
                    raised.
        :param dst: The destination of the symlink.  If it is a
                    directory, the basename of the source file will be
                    added.
        :param outside: If ``True``, the source filename is not
                        interpreted (unless ``dst`` is a directory).
                        If ``False`` (the default), the source
                        filename must be inside the tree.

        :returns: An ``FSEntry`` instance representing the new
                  symlink.
        """

        # Determine the destination
        dst = self._rel(dst)
        full_dst = self.tree._full(dst)

        # If the destination is a directory, we need to add the source
        # basename
        if os.path.isdir(full_dst):
            basename = os.path.basename(src)
            dst = os.path.join(dst, basename)
            full_dst = os.path.join(full_dst, basename)

        # Figure out the source
        if not outside:
            # Resolve to a tree path
            if isinstance(src, FSEntry):
                src = utils.abspath(src.name, cwd=self.name)
            else:
                src = utils.deroot(utils.abspath(src, cwd=self.path),
                                   self.tree.path)

            # We now have a tree-relative path, convert it into a path
            # relative to the destination
            src = str(utils.RelPath(src, dst))

        # Create the symlink
        os.symlink(src, full_dst)

        # Return a reference to the new file
        return self.tree._get(dst)

    def tar(self, filename, start=os.curdir, compression=utils.unset,
            hasher=None):
        """
        Create a tar file with the given filename.

        :param filename: The filename of the tar file to create.  If
                         ``compression`` is not given, it will be
                         inferred from the filename.  The appropriate
                         extensions will be added to the filename, if
                         necessary.  If a compression extension on the
                         filename does not match the specified
                         compression, a ``ValueError`` will be raised.
        :param start: The directory from which to start the tar
                      process.  If not given, starts from the current
                      directory and includes all files in the
                      directory.  If it is a parent of the current
                      directory, only the current directory will be
                      included in the tarball.  A ``ValueError`` will
                      be raised if the tar process cannot start from
                      the given location.
        :param compression: If given, specifies the compression to
                            use.  The ``filename`` will be modified to
                            include the appropriate extension.  A
                            ``ValueError`` will be raised if the given
                            compression is not supported or if a
                            compression was inferred from the
                            filename.
        :param hasher: If given, requests that a hash of the resulting
                       tar file be computed.  May be a ``True`` value
                       to use the default hasher; a string to specify
                       a hasher; or a tuple of hashers.

        :returns: The final filename that was created.  If ``hasher``
                  was specified, a tuple will be returned, with the
                  second element consisting of the hex digest of the
                  tar file.
        """

        # If the filename is a FSEntry, use its path
        if isinstance(filename, FSEntry):
            filename = filename.path

        # Parse the file name and set the compression
        filename = tarname.TarFileName(utils.abspath(filename, cwd=self.path))
        if compression is not utils.unset:
            filename.compression = compression

        # Determine the starting location and file list
        start = self._rel(start, False)
        filelist = None
        rel_path = utils.RelPath(start, self.name)
        if rel_path.parents and rel_path.remainder:
            raise ValueError("cannot start tar-ing from '%s'" % rel_path)
        elif not rel_path.parents and not rel_path.remainder:
            start = self.path
        elif rel_path.parents:
            start = os.path.normpath(
                os.path.join(self.path, [os.pardir] * rel_path.parents))
            filelist = [os.path.join(*rel_path.path_list[-rel_path.parents:])]
        start = self.tree._full(start)
        if filelist is None:
            filelist = os.listdir(start)

        # OK, let's build the tarball
        tar = tarfile.open(str(filename), 'w:%s' % filename.compression or '')
        try:
            with utils.workdir(start):
                for fname in filelist:
                    try:
                        tar.add(fname)
                    except Exception:
                        pass
        finally:
            tar.close()

        # Begin building the result
        result = str(filename)

        # If a hash was requested, generate it
        if hasher:
            # Select the hasher(s)
            if hasher is True:
                hasher = (utils.get_hasher(utils.DEFAULT_HASHER)(),)
            elif isinstance(hasher, six.string_types):
                hasher = (utils.get_hasher(hasher)(),)
            elif not isinstance(hasher, tuple):
                hasher = (hasher,)

            # Open the file
            with open(result) as f:
                result = (result, utils.digest(f, hasher))

        return result

    def utime(self, times=None):
        """
        Set the access and modified times for this file to the given
        values.  If no values are given, the access and modified times
        are set to the current time.

        :param times: If given, must be a tuple of the access time and
                      the modified time, as integers or floats.
        """

        os.utime(self.path, times)

    def walk(self, path=os.curdir, topdown=True, onerror=None,
             followlinks=False, absolute=False, ignore=None):
        """
        Walk the directory tree.  Similar to the ``os.walk()``
        generator.

        :param path: An optional path to a subelement of this
                     directory.
        :param topdown: If ``True`` (the default), the yielded tuple
                        for a directory is generated before that for
                        any of the subdirectories.  When ``True``, the
                        caller may modify the directory names list
                        in-place to influence how ``walk()`` recurses
                        through those directories.
        :param onerror: An optional callable that is called with the
                        ``OSError`` instance if an error occurs.  If
                        not provided, errors are ignored.
        :param followlinks: If ``False`` (the default), directories
                            pointed to by symbolic links will not be
                            traversed during the walk.
        :param absolute: If ``True``, the directory name returned as
                         part of the yielded tuple will be an absolute
                         path to the directory.  By default, this path
                         name will be relative to the tree root.
        :param ignore: An optional callable.  This callable will be
                       called with the absolute directory path and a
                       list of files and directories in that
                       directory; it should return a list of file and
                       directory names which should be subsequently
                       ignored.  Note that, if ``topdown`` is
                       ``False``, directories selected to be ignored
                       by this callable will be visited anyway.

        :returns: A generator yielding 3-tuples consisting of the name
                  of the directory, a list of subdirectories, and a
                  list of filenames.
        """

        # Walk the tree, starting from there
        for dirpath, dirnames, filenames in os.walk(self._abs(path), topdown,
                                                    onerror, followlinks):

            # Apply the ignore filter, if any
            utils.apply_ignore(ignore, dirpath, dirnames, filenames)

            if not absolute:
                # Trim the directory path
                dirpath = dirpath[len(self.tree.path):]

            yield dirpath, dirnames, filenames

    @cacheprop.cached_property
    def basename(self):
        """
        Retrieve the basename of the file entry.
        """

        return os.path.basename(self.name)

    @cacheprop.cached_property('st_mtime', base='stat')
    def contents(self):
        """
        Retrieve the contents of the file entry.  For directories,
        this will be a sorted list of the directory entries; for
        files, this will be the contents of the file.
        """

        # Check if it's a directory and return the directory entries
        if stat.S_ISDIR(self.stat_cached.st_mode):
            return sorted(os.listdir(self.path))

        # OK, read in the contents of the file
        with open(self.path) as f:
            return f.read()

    @cacheprop.cached_property
    def dirname(self):
        """
        Retrieve the dirname of the file entry.
        """

        return os.path.dirname(self.name)

    @cacheprop.cached_property
    def ext(self):
        """
        Retrieve the extension of the file entry.
        """

        return os.path.splitext(self.basename)[1]

    @property
    def isdir(self):
        """
        Determine if the file is a directory, returning ``True`` if it
        is.  This will follow symbolic links.
        """

        return stat.S_ISDIR(self.st_mode)

    @property
    def islink(self):
        """
        Determine if the file is a symbolic link, returning ``True``
        if it is.
        """

        return stat.S_ISLNK(self.lst_mode)

    @property
    def isfile(self):
        """
        Determine if the file is a regular file, returning ``True`` if
        it is.  This will follow symbolic links.
        """

        return stat.S_ISREG(self.st_mode)

    @cacheprop.cached_property('st_mtime', base='lstat')
    def lcontents(self):
        """
        Retrieve the contents of the file entry, not following
        symbolic links.  For symbolic links, this will be what the
        link points to.  For directories, this will be a sorted list
        of the directory entries; for files, this will be the contents
        of the file.
        """

        # Is it a link?
        if stat.S_ISLNK(self.lstat_cached.st_mode):
            return os.readlink(self.path)

        # Check if it's a directory and return the directory entries
        if stat.S_ISDIR(self.lstat_cached.st_mode):
            return sorted(os.listdir(self.path))

        # OK, read in the contents of the file
        with open(self.path) as f:
            return f.read()

    @property
    def lstat(self):
        """
        Retrieve the latest result of ``os.lstat()``.
        """

        self._lstat = os.lstat(self.path)
        return self._lstat

    @property
    def lstat_cached(self):
        """
        Retrieve the last cached result of ``os.lstat()``.
        """

        if self._lstat is utils.unset:
            return self.lstat
        return self._lstat

    @property
    def lpermissions(self):
        """
        Retrieve the permissions of the file, not following symlinks.
        """

        return stat.S_IMODE(self.lst_mode)

    @permissions.setter
    def lpermissions(self, value):
        """
        Set the permissions of the file, not following symlinks.
        """

        os.lchmod(self.path, value)

    @property
    def permissions(self):
        """
        Retrieve the permissions of the file.
        """

        return stat.S_IMODE(self.st_mode)

    @permissions.setter
    def permissions(self, value):
        """
        Set the permissions of the file.
        """

        os.chmod(self.path, value)

    @cacheprop.cached_property
    def realpath(self):
        """
        Retrieve the real path of the file entry.  This will have all
        symlinks resolved.
        """

        return os.path.realpath(self.path)

    @cacheprop.cached_property
    def root(self):
        """
        Retrieve the root name of the file entry, that is, the part of
        the basename that excludes the extension.
        """

        return os.path.splitext(self.basename)[0]

    @property
    def stat(self):
        """
        Retrieve the latest result of ``os.stat()``.
        """

        self._stat = os.stat(self.path)
        return self._stat

    @property
    def stat_cached(self):
        """
        Retrieve the last cached result of ``os.stat()``.
        """

        if self._stat is utils.unset:
            return self.stat
        return self._stat


class FSTree(FSEntry):
    """
    Represent a file system tree.  All accesses are constrained to
    occur within the tree.
    """

    def __init__(self, path, mode=0o777):
        """
        Initialize an ``FSTree`` instance.

        :param path: The path to the root of the tree.  If the path
                     does not exist, it will be created.
        :param mode: The mode for the root directory, if it does not
                     exist.  If the directory exists, the mode is
                     ignored.
        """

        # Make sure the path is absolute, then create it if it doesn't
        # exist
        path = utils.abspath(path)
        if not os.path.isdir(path):
            os.makedirs(path, mode)

        # Initialize the entry
        super(FSTree, self).__init__(self, '/', path)

        # Keep a weak dictionary of the entries
        self._entries = weakref.WeakValueDictionary()

    def _get(self, name, default=utils.unset):
        """
        Retrieve an ``FSEntry`` for the designated path.

        :param name: The tree-relative path to look up.
        :param default: A default value to return if the path doesn't
                        exist.  If not provided, a ``KeyError`` will
                        be raised.
        """

        # If name is us, return ourself
        if name == self.name:
            return self

        # Get the full path as well
        path = self._full(name)

        # Does the path even exist?
        if not os.path.exists(path):
            if default is utils.unset:
                raise KeyError(name)
            else:
                return default

        # OK, try to find an object for it
        entry = self._entries.get(name)
        if not entry:
            entry = FSEntry(self, name, path)
            self._entries[name] = entry

        return entry

    def _set(self, name, value):
        """
        Set the ``FSEntry`` for a given path.

        :param name: The name to set to the given value.
        :param value: The value to set.  If a string, the value is
                      interpreted as an absolute filesystem location
                      to copy from; if it is an ``FSEntry`` in this
                      tree, it will be moved to this location; and if
                      it is an ``FSEntry`` from another tree, it will
                      be copied to this location.  If the value is a
                      callable, it will be called with the tree and
                      the destination name; see the ``Assignable``
                      subclasses.
        """

        # First, we can't set ourself
        if name == self.name:
            raise ValueError("cannot overwrite tree root")

        # OK, check the type of the value
        if isinstance(value, six.string_types):
            self.copy(value, name)
        elif isinstance(value, FSEntry):
            if value.tree is self:
                # Move the file
                self.move(value, name)
            else:
                # Copy the file
                self.copy(value, name)
        elif callable(value):
            value(self, name)

        # Don't know what to do with it
        raise ValueError("cannot assign a %r to a file" % value)

    def _del(self, name):
        """
        Delete the ``FSEntry`` for a given path.

        :param name: The name to delete.
        """

        # First, we can't delete ourself
        if name == self.name:
            raise ValueError("cannot delete tree root")

        # Remove the file
        self.remove(name)

    def _full(self, name):
        """
        Determine the full path to a named file.

        :param name: The name to resolve to a full path.
        """

        return os.path.join(self.path, name[1:])

    def cleanup(self):
        """
        Cleans up the file tree.  This will remove the tree and all
        its files.
        """

        # Clean up!
        shutil.rmtree(self.path)
