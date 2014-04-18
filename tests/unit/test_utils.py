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

import hashlib
import io
import unittest

import mock
import six

from fstree import utils

import tests


class DerootTest(unittest.TestCase):
    def test_slash(self):
        result = utils.deroot('/foo/bar')

        self.assertEqual(result, '/foo/bar')

    def test_short(self):
        self.assertRaises(ValueError, utils.deroot, '/foo/b', '/foo/bar')

    def test_unequal(self):
        self.assertRaises(ValueError, utils.deroot, '/foo/baz/qux', '/foo/bar')

    def test_nosep(self):
        self.assertRaises(ValueError, utils.deroot, '/foo/barr', '/foo/bar')

    def test_exact(self):
        result = utils.deroot('/foo/bar', '/foo/bar')

        self.assertEqual(result, '/')

    def test_normal(self):
        result = utils.deroot('/foo/bar/baz/quux', '/foo/bar')

        self.assertEqual(result, '/baz/quux')


class AbsPathTest(unittest.TestCase):
    @mock.patch('os.path.abspath', side_effect=lambda x: x)
    @mock.patch('os.getcwd', return_value='/current/dir')
    @mock.patch.object(utils, 'deroot', return_value='/root')
    def test_absolute(self, mock_deroot, mock_getcwd, mock_abspath):
        result = utils.abspath('/foo//bar/..///baz')

        self.assertEqual(result, '/foo/baz')
        mock_abspath.assert_called_once_with('/')
        self.assertFalse(mock_getcwd.called)
        self.assertFalse(mock_deroot.called)

    @mock.patch('os.path.abspath', side_effect=lambda x: x)
    @mock.patch('os.getcwd', return_value='/current/dir')
    @mock.patch.object(utils, 'deroot', return_value='/root')
    def test_relative(self, mock_deroot, mock_getcwd, mock_abspath):
        result = utils.abspath('foo//bar/..///baz', root='/root')

        self.assertEqual(result, '/root/foo/baz')
        mock_abspath.assert_called_once_with('/root')
        mock_getcwd.assert_called_once_with()
        mock_deroot.assert_called_once_with('/current/dir', '/root')

    if six.PY2:
        @mock.patch('os.path.abspath', side_effect=lambda x: x)
        @mock.patch('os.getcwd', return_value='/current/dir')
        @mock.patch('os.getcwdu', return_value='/unicode/dir')
        @mock.patch.object(utils, 'deroot', return_value='/root')
        def test_relative_py2(self, mock_deroot, mock_getcwdu, mock_getcwd,
                              mock_abspath):
            result = utils.abspath(u'foo//bar/..///baz', root='/root')

            self.assertEqual(result, '/root/foo/baz')
            mock_abspath.assert_called_once_with('/root')
            self.assertFalse(mock_getcwd.called)
            mock_getcwdu.assert_called_once_with()
            mock_deroot.assert_called_once_with('/unicode/dir', '/root')

    @mock.patch('os.path.abspath', side_effect=lambda x: x)
    @mock.patch('os.getcwd', return_value='/current/dir')
    @mock.patch.object(utils, 'deroot', return_value='/root')
    def test_relative_with_cwd(self, mock_deroot, mock_getcwd, mock_abspath):
        result = utils.abspath('foo//bar/..///baz', cwd='/curr')

        self.assertEqual(result, '/curr/foo/baz')
        mock_abspath.assert_called_once_with('/')
        self.assertFalse(mock_getcwd.called)
        self.assertFalse(mock_deroot.called)


class RelPathTest(unittest.TestCase):
    @mock.patch.object(utils, 'abspath', side_effect=lambda x, y: x)
    def test_init_nopath(self, mock_abspath):
        self.assertRaises(ValueError, utils.RelPath, '')
        self.assertFalse(mock_abspath.called)

    @mock.patch.object(utils, 'abspath', side_effect=lambda x, y: x)
    def test_init_normal(self, mock_abspath):
        result = utils.RelPath('/path/1', '/path/2')

        self.assertEqual(result.path_list, ['path', '1'])
        self.assertEqual(result.parents, 1)
        self.assertEqual(result.remainder, '1')
        mock_abspath.assert_has_calls([
            mock.call('/path/1', '/'),
            mock.call('/path/2', '/'),
        ])

    @mock.patch.object(utils, 'abspath', side_effect=lambda x, y: x)
    def test_init_alt_root(self, mock_abspath):
        result = utils.RelPath('/path/1', '/path/2', '/root')

        self.assertEqual(result.path_list, ['path', '1'])
        self.assertEqual(result.parents, 1)
        self.assertEqual(result.remainder, '1')
        mock_abspath.assert_has_calls([
            mock.call('/path/1', '/root'),
            mock.call('/path/2', '/root'),
        ])

    @mock.patch.object(utils, 'abspath', side_effect=lambda x, y: x)
    def test_init_deeper(self, mock_abspath):
        result = utils.RelPath('/path/1/sub/directory', '/path/1')

        self.assertEqual(result.path_list, ['path', '1', 'sub', 'directory'])
        self.assertEqual(result.parents, 0)
        self.assertEqual(result.remainder, 'sub/directory')
        mock_abspath.assert_has_calls([
            mock.call('/path/1/sub/directory', '/'),
            mock.call('/path/1', '/'),
        ])

    @mock.patch.object(utils, 'abspath', side_effect=lambda x, y: x)
    def test_init_super_parent(self, mock_abspath):
        result = utils.RelPath('/path/1', '/path/1/sub/directory')

        self.assertEqual(result.path_list, ['path', '1'])
        self.assertEqual(result.parents, 2)
        self.assertEqual(result.remainder, '')
        mock_abspath.assert_has_calls([
            mock.call('/path/1', '/'),
            mock.call('/path/1/sub/directory', '/'),
        ])

    @mock.patch.object(utils, 'abspath', side_effect=lambda x, y: x)
    def test_init_equal(self, mock_abspath):
        result = utils.RelPath('/path/1', '/path/1')

        self.assertEqual(result.path_list, ['path', '1'])
        self.assertEqual(result.parents, 0)
        self.assertEqual(result.remainder, '')
        mock_abspath.assert_has_calls([
            mock.call('/path/1', '/'),
            mock.call('/path/1', '/'),
        ])

    @mock.patch.object(utils, 'abspath', side_effect=lambda x, y: x)
    def test_str_deeper(self, mock_abspath):
        result = utils.RelPath('/path/1/sub/directory', '/path/1')

        self.assertEqual(str(result), 'sub/directory')

    @mock.patch.object(utils, 'abspath', side_effect=lambda x, y: x)
    def test_str_super_parent(self, mock_abspath):
        result = utils.RelPath('/path/1', '/path/1/sub/directory')

        self.assertEqual(str(result), '../..')

    @mock.patch.object(utils, 'abspath', side_effect=lambda x, y: x)
    def test_str_equal(self, mock_abspath):
        result = utils.RelPath('/path/1', '/path/1')

        self.assertEqual(str(result), '.')


class WorkDirTest(unittest.TestCase):
    @mock.patch('os.getcwd', return_value='/c/w/d')
    @mock.patch('os.chdir')
    def test_basic(self, mock_chdir, mock_getcwd):
        with utils.workdir('/test/path') as cwd:
            self.assertEqual(cwd, '/c/w/d')

        mock_getcwd.assert_called_once_with()
        mock_chdir.assert_has_calls([
            mock.call('/test/path'),
            mock.call('/c/w/d'),
        ])

    @mock.patch('os.getcwd', return_value='/c/w/d')
    @mock.patch('os.chdir')
    def test_exception(self, mock_chdir, mock_getcwd):
        try:
            with utils.workdir('/test/path') as cwd:
                self.assertEqual(cwd, '/c/w/d')
                raise tests.TestException('test')
        except tests.TestException:
            pass
        else:
            self.fail("Failed to bubble up raised exception")

        mock_getcwd.assert_called_once_with()
        mock_chdir.assert_has_calls([
            mock.call('/test/path'),
            mock.call('/c/w/d'),
        ])


class GetHasherTest(unittest.TestCase):
    def test_md5(self):
        result = utils.get_hasher('md5')

        self.assertEqual(result, hashlib.md5)

    def test_sha1(self):
        result = utils.get_hasher('sha1')

        self.assertEqual(result, hashlib.sha1)


class DigestTest(unittest.TestCase):
    @mock.patch.object(utils, 'BLOCKSIZE', 4)
    def test_basic(self):
        fo = io.BytesIO(six.b("12345678901234"))
        digesters = [
            mock.Mock(**{'hexdigest.return_value': 'd16e57'}),
            mock.Mock(),
            mock.Mock(),
        ]

        result = utils.digest(fo, digesters)

        self.assertEqual(result, 'd16e57')
        for i, digester in enumerate(digesters):
            digester.update.assert_has_calls([
                mock.call(six.b('1234')),
                mock.call(six.b('5678')),
                mock.call(six.b('9012')),
                mock.call(six.b('34')),
            ])
            self.assertEqual(digester.update.call_count, 4)
            if i == 0:
                digester.hexdigest.assert_called_once_with()
            else:
                self.assertFalse(digester.hexdigest.called)


class ApplyIgnoreTest(unittest.TestCase):
    def test_no_ignore(self):
        dirs = ['a', 'b', 'c']
        files = ['z', 'y', 'x']

        utils.apply_ignore(None, '/dir/path', dirs, files)

        self.assertEqual(dirs, ['a', 'b', 'c'])
        self.assertEqual(files, ['z', 'y', 'x'])

    def test_with_ignore(self):
        ignore = mock.Mock(return_value=['b', 'y'])
        dirs = ['a', 'b', 'c']
        files = ['z', 'y', 'x']

        utils.apply_ignore(ignore, '/dir/path', dirs, files)

        ignore.assert_called_once_with('/dir/path',
                                       ['a', 'b', 'c', 'z', 'y', 'x'])
        self.assertEqual(dirs, ['a', 'c'])
        self.assertEqual(files, ['z', 'x'])
