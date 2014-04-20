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

import unittest

import mock

from fstree import tarname
from fstree import utils


class CompressionTest(unittest.TestCase):
    @mock.patch.dict(tarname.Compression._compressions, clear=True)
    def test_lookup_compression_missing(self):
        result = tarname.Compression.lookup_compression('test')

        self.assertEqual(result, None)

    @mock.patch.dict(tarname.Compression._compressions, clear=True,
                     test='compression')
    def test_lookup_compression_missing(self):
        result = tarname.Compression.lookup_compression('test')

        self.assertEqual(result, 'compression')

    @mock.patch.dict(tarname.Compression._extensions, clear=True)
    def test_lookup_extension_missing(self):
        result = tarname.Compression.lookup_extension('.test')

        self.assertEqual(result, None)

    @mock.patch.dict(tarname.Compression._extensions, clear=True,
                     test='extension')
    def test_lookup_extension_missing(self):
        result = tarname.Compression.lookup_extension('.test')

        self.assertEqual(result, 'extension')

    @mock.patch.dict(tarname.Compression._compressions, clear=True,
                     test='compression')
    @mock.patch.dict(tarname.Compression._extensions, clear=True)
    def test_new_exists(self):
        self.assertRaises(ValueError, tarname.Compression, 'test', True,
                          'test')

    @mock.patch.dict(tarname.Compression._compressions, clear=True)
    @mock.patch.dict(tarname.Compression._extensions, clear=True)
    def test_new_noext(self):
        self.assertRaises(ValueError, tarname.Compression, 'test', True)

    @mock.patch.dict(tarname.Compression._compressions, clear=True)
    @mock.patch.dict(tarname.Compression._extensions, clear=True,
                     test='extension')
    def test_new_collision(self):
        self.assertRaises(ValueError, tarname.Compression, 'test', True,
                          'test')

    @mock.patch.dict(tarname.Compression._compressions, clear=True,
                     other='compression')
    @mock.patch.dict(tarname.Compression._extensions, clear=True,
                     other='extension')
    def test_new(self):
        comp = tarname.Compression('test', True, 't1', 't2', 't3')

        self.assertEqual(comp.name, 'test')
        self.assertEqual(comp.supported, True)
        self.assertEqual(comp.extension, '.t1')
        self.assertEqual(tarname.Compression._compressions, {
            'other': 'compression',
            'test': comp,
        })
        self.assertEqual(tarname.Compression._extensions, {
            'other': 'extension',
            't1': {'compression': comp},
            't2': {'compression': comp, 'has_tar_ext': True},
            't3': {'compression': comp, 'has_tar_ext': True},
        })

    @mock.patch.dict(tarname.Compression._compressions, clear=True)
    @mock.patch.dict(tarname.Compression._extensions, clear=True)
    def test_str(self):
        comp = tarname.Compression('test', True, 'test')

        self.assertEqual(str(comp), 'test')


class TarFileNameTest(unittest.TestCase):
    @mock.patch.object(tarname.Compression, 'lookup_extension',
                       return_value=None)
    def test_init_basename(self, mock_lookup_extension):
        result = tarname.TarFileName('/foo/bar/basename')

        self.assertEqual(result.basename, '/foo/bar/basename')
        self.assertEqual(result.extensions, ['.tar'])
        self.assertEqual(result._compression, utils.unset)
        self.assertFalse(mock_lookup_extension.called)

    @mock.patch.object(tarname.Compression, 'lookup_extension',
                       return_value=None)
    def test_init_ext_unknown(self, mock_lookup_extension):
        result = tarname.TarFileName('/foo/bar/basename.ext1.ext2')

        self.assertEqual(result.basename, '/foo/bar/basename.ext1.ext2')
        self.assertEqual(result.extensions, ['.tar'])
        self.assertEqual(result._compression, utils.unset)
        mock_lookup_extension.assert_called_once_with('.ext2')

    @mock.patch.object(tarname.Compression, 'lookup_extension')
    def test_init_tar_ext(self, mock_lookup_extension):
        gz = mock.Mock(__str__=mock.Mock(return_value='gz'),
                       supported=True)
        exts = {
            '.tar': {'has_tar_ext': True},
            '.gz': {'compression': gz},
        }
        mock_lookup_extension.side_effect = lambda x: exts[x]

        result = tarname.TarFileName('/foo/bar/basename.ext.gz.tar')

        self.assertEqual(result.basename, '/foo/bar/basename.ext.gz')
        self.assertEqual(result.extensions, ['.tar'])
        self.assertEqual(result._compression, utils.unset)
        mock_lookup_extension.assert_called_once_with('.tar')

    @mock.patch.object(tarname.Compression, 'lookup_extension')
    def test_init_tgz_ext(self, mock_lookup_extension):
        gz = mock.Mock(__str__=mock.Mock(return_value='gz'),
                       supported=True)
        exts = {
            '.tgz': {'compression': gz, 'has_tar_ext': True},
            '.gz': {'compression': gz},
        }
        mock_lookup_extension.side_effect = lambda x: exts[x]

        result = tarname.TarFileName('/foo/bar/basename.ext.gz.tgz')

        self.assertEqual(result.basename, '/foo/bar/basename.ext.gz')
        self.assertEqual(result.extensions, ['.tgz'])
        self.assertEqual(result._compression, gz)
        mock_lookup_extension.assert_called_once_with('.tgz')

    @mock.patch.object(tarname.Compression, 'lookup_extension')
    def test_init_duplicate_compression(self, mock_lookup_extension):
        gz = mock.Mock(__str__=mock.Mock(return_value='gz'),
                       supported=True)
        exts = {
            '.gz': {'compression': gz},
        }
        mock_lookup_extension.side_effect = lambda x: exts[x]

        self.assertRaises(ValueError, tarname.TarFileName,
                          '/foo/bar/basename.ext.gz.gz')

        mock_lookup_extension.assert_has_calls([
            mock.call('.gz'),
            mock.call('.gz'),
        ])

    @mock.patch.object(tarname.Compression, 'lookup_extension')
    def test_init_double_compression(self, mock_lookup_extension):
        gz = mock.Mock(__str__=mock.Mock(return_value='gz'),
                       supported=True)
        bz2 = mock.Mock(__str__=mock.Mock(return_value='bz2'),
                        supported=True)
        exts = {
            '.gz': {'compression': gz},
            '.bz2': {'compression': bz2},
        }
        mock_lookup_extension.side_effect = lambda x: exts[x]

        self.assertRaises(ValueError, tarname.TarFileName,
                          '/foo/bar/basename.ext.gz.bz2')

        mock_lookup_extension.assert_has_calls([
            mock.call('.bz2'),
            mock.call('.gz'),
        ])

    @mock.patch.object(tarname.Compression, 'lookup_extension')
    def test_init_unsupported_compression(self, mock_lookup_extension):
        lzo = mock.Mock(__str__=mock.Mock(return_value='lzo'),
                        supported=False)
        exts = {
            '.lzo': {'compression': lzo},
        }
        mock_lookup_extension.side_effect = lambda x: exts[x]

        self.assertRaises(ValueError, tarname.TarFileName,
                          '/foo/bar/basename.ext.lzo')

        mock_lookup_extension.assert_called_once_with('.lzo')

    @mock.patch.object(tarname.Compression, 'lookup_extension')
    def test_init_missing_tar_compression(self, mock_lookup_extension):
        gz = mock.Mock(__str__=mock.Mock(return_value='gz'),
                       supported=True)
        exts = {
            '.tar': {'has_tar_ext': True},
            '.gz': {'compression': gz},
        }
        mock_lookup_extension.side_effect = lambda x: exts[x]

        self.assertRaises(ValueError, tarname.TarFileName,
                          '/foo/bar/basename.gz')

        mock_lookup_extension.assert_called_once_with('.gz')

    def make_tarfile(self, basename, extensions, compression):
        with mock.patch.object(tarname.TarFileName, '__init__',
                               return_value=None):
            obj = tarname.TarFileName()

        obj.basename = basename
        obj.extensions = extensions
        obj._compression = compression
        return obj

    def test_str(self):
        obj = self.make_tarfile('/foo/bar/basename', ['.tar', '.gz'],
                                utils.unset)

        self.assertEqual(str(obj), '/foo/bar/basename.tar.gz')

    def test_compression_get_unset(self):
        obj = self.make_tarfile('/foo/bar/basename', ['.tar'], utils.unset)

        self.assertEqual(obj.compression, None)

    def test_compression_get_none(self):
        obj = self.make_tarfile('/foo/bar/basename', ['.tar'], None)

        self.assertEqual(obj.compression, None)

    def test_compression_get_something(self):
        obj = self.make_tarfile('/foo/bar/basename', ['.tar'], 'something')

        self.assertEqual(obj.compression, 'something')

    @mock.patch.object(tarname.Compression, 'lookup_compression',
                       return_value=mock.Mock(extension='.gz', supported=True))
    def test_compression_set_set(self, mock_lookup_compression):
        obj = self.make_tarfile('/foo/bar/basename', ['.tar'], None)

        def test_func():
            obj.compression = 'something'

        self.assertRaises(ValueError, test_func)
        self.assertFalse(mock_lookup_compression.called)

    @mock.patch.object(tarname.Compression, 'lookup_compression',
                       return_value=None)
    def test_compression_set_unknown(self, mock_lookup_compression):
        obj = self.make_tarfile('/foo/bar/basename', ['.tar'], utils.unset)

        def test_func():
            obj.compression = 'something'

        self.assertRaises(ValueError, test_func)
        mock_lookup_compression.assert_called_once_with('something')

    @mock.patch.object(tarname.Compression, 'lookup_compression',
                       return_value=mock.Mock(extension='.lzo',
                                              supported=False))
    def test_compression_set_unsupported(self, mock_lookup_compression):
        obj = self.make_tarfile('/foo/bar/basename', ['.tar'], utils.unset)

        def test_func():
            obj.compression = 'something'

        self.assertRaises(ValueError, test_func)
        mock_lookup_compression.assert_called_once_with('something')

    @mock.patch.object(tarname.Compression, 'lookup_compression',
                       return_value=mock.Mock(extension='.gz', supported=True))
    def test_compression_set_none(self, mock_lookup_compression):
        obj = self.make_tarfile('/foo/bar/basename', ['.tar'], utils.unset)

        obj.compression = None

        self.assertFalse(mock_lookup_compression.called)
        self.assertEqual(obj.extensions, ['.tar'])
        self.assertEqual(obj._compression, None)

    @mock.patch.object(tarname.Compression, 'lookup_compression',
                       return_value=mock.Mock(extension='.gz', supported=True))
    def test_compression_set_something(self, mock_lookup_compression):
        obj = self.make_tarfile('/foo/bar/basename', ['.tar'], utils.unset)

        obj.compression = 'something'

        mock_lookup_compression.assert_called_once_with('something')
        self.assertEqual(obj.extensions, ['.tar', '.gz'])
        self.assertEqual(obj._compression,
                         mock_lookup_compression.return_value)

    @mock.patch.object(tarname.Compression, 'lookup_compression',
                       return_value=mock.Mock(extension='.gz', supported=True))
    def test_compression_set_compression(self, mock_lookup_compression):
        comp = mock.Mock(
            extension='.bz2',
            supported=True,
            spec=tarname.Compression,
        )
        obj = self.make_tarfile('/foo/bar/basename', ['.tar'], utils.unset)

        obj.compression = comp

        self.assertFalse(mock_lookup_compression.called)
        self.assertEqual(obj.extensions, ['.tar', '.bz2'])
        self.assertEqual(obj._compression, comp)
