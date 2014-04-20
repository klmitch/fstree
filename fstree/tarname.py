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

import six

from fstree import utils


class Compression(object):
    """
    Represent compression formats compatible with tar.  Not every
    format is supported by ``fstree``, but the data is needed for
    parsing tar file names.
    """

    # A registry of compression information
    _compressions = {}

    # A registry of extension information
    _extensions = {
        'tar': {'has_tar_ext': True},
    }

    @classmethod
    def lookup_compression(cls, name):
        """
        Retrieve the requested compression format descriptor.

        :param name: The name of the requested compression.

        :returns: A description of the requested compression format,
                  or ``None`` if the requested compression format has
                  not been declared.
        """

        return cls._compressions.get(name)

    @classmethod
    def lookup_extension(cls, ext):
        """
        Retrieve the requested extension descriptor.

        :param ext: The extension for the requested compression.

        :returns: A dictionary having at least one of the two keys
                  "compression" and "has_tar_ext".  The "compression"
                  key corresponds to the registered compression, and
                  the "has_tar_ext" key is a boolean indicating
                  whether the extension is a combination with the
                  ".tar" extension.  If the requested extension cannot
                  be found, returns ``None``.
        """

        return cls._extensions.get(ext[1:])

    def __new__(cls, name, supported, *extensions):
        """
        Retrieve the description of a tar-compatible compression
        format.

        :param name: The name of the compression.
        :param supported: A boolean indicating whether the compression
                          format is supported.  This may vary based on
                          the version of Python.
        :param extensions: Remaining arguments specify file extensions
                           corresponding to the format.  The first
                           extension is designated the preferred
                           extension, and remaining extensions are
                           assumed to be combinations with the ".tar"
                           extension.  Extensions should be specified
                           without a leading ".".

        :returns: The declared compression format.
        """

        # Don't allow duplicates
        if name in cls._compressions:
            raise ValueError("compression format %s already declared" % name)

        # Require at least one extension
        if not extensions:
            raise ValueError("at least one extension must be provided")

        # Don't allow extension collisions
        collisions = [
            "'.%s' in compression %s" % (ext, cls._extensions[ext])
            for ext in extensions if ext in cls._extensions
        ]
        if collisions:
            raise ValueError(
                "extensions already declared for other compressions: %s" %
                '; '.join(collisions))

        # Create the compression
        obj = super(Compression, cls).__new__(cls)
        obj.name = name
        obj.supported = supported
        obj.extension = '.' + extensions[0]

        # Update the extensions registry
        cls._extensions.update(
            (ext, ({'compression': obj} if i == 0 else
                   {'compression': obj, 'has_tar_ext': True}))
            for i, ext in enumerate(extensions))

        # Cache the compression description
        cls._compressions[name] = obj

        # Return the compression
        return obj

    def __str__(self):
        """
        Retrieve the string form of the compression (its name).
        """

        return self.name


# This data culled from tar/src/suffix.c in the gnu tar sources
Compression('gz', True, 'gz', 'tgz', 'taz')
Compression('Z', False, 'Z', 'taZ')
Compression('bz2', True, 'bz2', 'tbz', 'tbz2', 'tz2')
Compression('lz', False, 'lz')
Compression('lzma', False, 'lzma', 'tlz')
Compression('lzo', False, 'lzo')
Compression('xz', six.PY3, 'xz', 'txz')


class TarFileName(object):
    """
    Represent the file name of a tar file.  The ``basename`` attribute
    contains the base name of the tar file, and ``extensions`` is a
    list of extensions in order.  The ``compression`` property
    contains the name of the compression scheme to use, if any, and
    may be set if the compression was not specified as part of the
    file name.
    """

    def __init__(self, filename):
        """
        Initialize a ``TarFileName`` object.  Parses the given
        filename and determines the correct extensions and compression
        algorithm to use.

        :param filename: The filename to use for the tar file.
        """

        # Prepare for the filename parser
        dirname, basename = os.path.split(filename)
        extensions = []
        state = {
            'compression': utils.unset,
            'has_tar_ext': False,
        }

        while not state['has_tar_ext']:
            # Get the next extension and its descriptor
            root, ext = os.path.splitext(basename)
            data = ext and Compression.lookup_extension(ext)
            if not ext or not data:
                break

            # If it contains compression, do some sanity checks
            if 'compression' in data:
                # Make sure compression hasn't been set yet
                if state['compression'] is not utils.unset:
                    if state['compression'] is data['compression']:
                        raise ValueError("tar filename references '%s' twice" %
                                         data['compression'])
                    raise ValueError("tar filename contains both '%s' and "
                                     "'%s' compression" %
                                     (data['compression'],
                                      state['compression']))

                # Make sure compression is supported
                if not data['compression'].supported:
                    raise ValueError("compression format '%s' not supported" %
                                     data['compression'])

            # Update the state and save the extension
            extensions.insert(0, ext)
            state.update(data)
            basename = root

        # Did we get a compression without a '.tar' extension?
        if (state['compression'] is not utils.unset and
                not state['has_tar_ext']):
            raise ValueError("tar filename contains '%s' compression but "
                             "no '.tar' extension" % state['compression'])

        # Make sure we have a .tar extension
        if not state['has_tar_ext']:
            extensions.insert(0, '.tar')

        # Assemble the filename and save the compression
        self.basename = os.path.join(dirname, basename)
        self.extensions = extensions
        self._compression = state['compression']

    def __str__(self):
        """
        Retrieve the string form of the tar file name.  This will be
        the file base name plus all the defined extensions.
        """

        return self.basename + ''.join(self.extensions)

    @property
    def compression(self):
        """
        Retrieve the designated compression for the tar file.
        """

        return None if self._compression is utils.unset else self._compression

    @compression.setter
    def compression(self, compression):
        """
        Set the desired compression.  This will update the extensions
        to include the appropriate compression extension.

        :param compression: The desired compression.
        """

        # Don't allow changing the compression
        if self._compression is not utils.unset:
            raise ValueError("compression is already set to '%s'" %
                             self._compression)

        # Make sure the compression is supported
        if compression:
            if not isinstance(compression, Compression):
                descriptor = Compression.lookup_compression(compression)
                if not descriptor:
                    raise ValueError("unknown compression scheme '%s'" %
                                     compression)
                compression = descriptor
            if not compression.supported:
                raise ValueError("compression scheme '%s' is unsupported" %
                                 compression)

            # Set the extension
            self.extensions.append(compression.extension)

        # Save the designated compression
        self._compression = compression
