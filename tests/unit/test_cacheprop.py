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
from six.moves import builtins

from fstree import cacheprop


class CachePropertyTest(unittest.TestCase):
    @mock.patch('operator.attrgetter', side_effect=lambda x: x)
    def test_init(self, mock_attrgetter):
        def test_func():
            pass

        result = cacheprop.CacheProperty(test_func, ['a', 'b', 'c'], 'base')

        self.assertEqual(result.func, test_func)
        self.assertEqual(result.prop, 'test_func')
        self.assertEqual(result.cache_attr, '_test_func')
        self.assertEqual(result.attrs, {'a': 'a', 'b': 'b', 'c': 'c'})
        self.assertEqual(result.base, 'base')
        mock_attrgetter.assert_has_calls([
            mock.call('a'),
            mock.call('b'),
            mock.call('c'),
        ])
        self.assertEqual(mock_attrgetter.call_count, 3)

    def test_call_ctrl_missing(self):
        def test_prop(obj):
            return 'prop'
        obj = mock.Mock(
            spec=['_test_prop', 'a', 'b'],
            _test_prop='cached',
            a=1,
            b=2,
        )
        cacher = cacheprop.CacheProperty(test_prop, ['a', 'b'], lambda x: x)

        result = cacher(obj)

        self.assertEqual(result, 'prop')
        self.assertEqual(obj.__cache_control__,
                         {'test_prop': {'a': 1, 'b': 2}})
        self.assertEqual(obj._test_prop, 'prop')

    def test_call_set_noctrl(self):
        def test_prop(obj):
            return 'prop'
        obj = mock.Mock(
            spec=['__cache_control__', '_test_prop'],
            __cache_control__={'test_prop': {}, 'other': 'test'},
            _test_prop='cached',
        )
        cacher = cacheprop.CacheProperty(test_prop, [], lambda x: x)

        result = cacher(obj)

        self.assertEqual(result, 'cached')
        self.assertEqual(obj.__cache_control__,
                         {'test_prop': {}, 'other': 'test'})
        self.assertEqual(obj._test_prop, 'cached')

    def test_call_unset_noctrl(self):
        def test_prop(obj):
            return 'prop'
        obj = mock.Mock(
            spec=['__cache_control__'],
            __cache_control__={'test_prop': {}, 'other': 'test'},
        )
        cacher = cacheprop.CacheProperty(test_prop, [], lambda x: x)

        result = cacher(obj)

        self.assertEqual(result, 'prop')
        self.assertEqual(obj.__cache_control__,
                         {'test_prop': {}, 'other': 'test'})
        self.assertEqual(obj._test_prop, 'prop')

    def test_call_set_ctrl(self):
        def test_prop(obj):
            return 'prop'
        obj = mock.Mock(
            spec=['__cache_control__', '_test_prop', 'a', 'b'],
            __cache_control__={'test_prop': {'a': 1, 'b': 2}, 'other': 'test'},
            _test_prop='cached',
            a=1,
            b=2,
        )
        cacher = cacheprop.CacheProperty(test_prop, ['a', 'b'], lambda x: x)

        result = cacher(obj)

        self.assertEqual(result, 'cached')
        self.assertEqual(obj.__cache_control__,
                         {'test_prop': {'a': 1, 'b': 2}, 'other': 'test'})
        self.assertEqual(obj._test_prop, 'cached')

    def test_call_set_ctrl_outdated(self):
        def test_prop(obj):
            return 'prop'
        obj = mock.Mock(
            spec=['__cache_control__', '_test_prop', 'a', 'b'],
            __cache_control__={'test_prop': {'a': 1, 'b': 2}, 'other': 'test'},
            _test_prop='cached',
            a=2,
            b=4,
        )
        cacher = cacheprop.CacheProperty(test_prop, ['a', 'b'], lambda x: x)

        result = cacher(obj)

        self.assertEqual(result, 'prop')
        self.assertEqual(obj.__cache_control__,
                         {'test_prop': {'a': 2, 'b': 4}, 'other': 'test'})
        self.assertEqual(obj._test_prop, 'prop')

    def test_call_unset_ctrl(self):
        def test_prop(obj):
            return 'prop'
        obj = mock.Mock(
            spec=['__cache_control__', 'a', 'b'],
            __cache_control__={'test_prop': {'a': 1, 'b': 2}, 'other': 'test'},
            a=1,
            b=2,
        )
        cacher = cacheprop.CacheProperty(test_prop, ['a', 'b'], lambda x: x)

        result = cacher(obj)

        self.assertEqual(result, 'prop')
        self.assertEqual(obj.__cache_control__,
                         {'test_prop': {'a': 1, 'b': 2}, 'other': 'test'})
        self.assertEqual(obj._test_prop, 'prop')

    def test_call_ctrl_missing(self):
        def test_prop(obj):
            return 'prop'
        obj = mock.Mock(
            spec=['_test_prop', 'a', 'b'],
            _test_prop='cached',
            a=1,
            b=2,
        )
        cacher = cacheprop.CacheProperty(test_prop, ['a', 'b'], lambda x: x)

        result = cacher(obj)

        self.assertEqual(result, 'prop')
        self.assertEqual(obj.__cache_control__,
                         {'test_prop': {'a': 1, 'b': 2}})
        self.assertEqual(obj._test_prop, 'prop')


class CachedPropertyDecoratorTest(unittest.TestCase):
    @mock.patch.object(builtins, 'property', side_effect=lambda x: x)
    def test_no_args(self, mock_property):
        def func():
            pass

        decorator = cacheprop.cached_property()

        self.assertTrue(callable(decorator))
        self.assertFalse(isinstance(decorator, cacheprop.CacheProperty))
        self.assertFalse(mock_property.called)

        result = decorator(func)

        self.assertTrue(isinstance(result, cacheprop.CacheProperty))
        mock_property.assert_called_once_with(result)
        self.assertEqual(result.func, func)
        self.assertEqual(result.prop, 'func')
        self.assertEqual(result.cache_attr, '_func')
        self.assertEqual(result.attrs, {})
        self.assertEqual(result.base('spam'), 'spam')

    @mock.patch.object(builtins, 'property', side_effect=lambda x: x)
    def test_with_base(self, mock_property):
        def func():
            pass

        decorator = cacheprop.cached_property(base='foo')

        self.assertTrue(callable(decorator))
        self.assertFalse(isinstance(decorator, cacheprop.CacheProperty))
        self.assertFalse(mock_property.called)

        result = decorator(func)

        self.assertTrue(isinstance(result, cacheprop.CacheProperty))
        mock_property.assert_called_once_with(result)
        self.assertEqual(result.func, func)
        self.assertEqual(result.prop, 'func')
        self.assertEqual(result.cache_attr, '_func')
        self.assertEqual(result.attrs, {})
        self.assertEqual(result.base(mock.Mock(foo='spam')), 'spam')

    @mock.patch.object(builtins, 'property', side_effect=lambda x: x)
    def test_with_attrs(self, mock_property):
        def func():
            pass

        decorator = cacheprop.cached_property('a', 'b', 'c')

        self.assertTrue(callable(decorator))
        self.assertFalse(isinstance(decorator, cacheprop.CacheProperty))
        self.assertFalse(mock_property.called)

        result = decorator(func)

        self.assertTrue(isinstance(result, cacheprop.CacheProperty))
        mock_property.assert_called_once_with(result)
        self.assertEqual(result.func, func)
        self.assertEqual(result.prop, 'func')
        self.assertEqual(result.cache_attr, '_func')
        self.assertEqual(len(result.attrs), 3)
        for attr, getter in result.attrs.items():
            self.assertTrue(attr in 'abc')
            self.assertEqual(getter(mock.Mock(**{attr: 'spam'})), 'spam')
        self.assertEqual(result.base('spam'), 'spam')

    @mock.patch.object(builtins, 'property', side_effect=lambda x: x)
    def test_with_func_only(self, mock_property):
        def func():
            pass

        result = cacheprop.cached_property(func)

        self.assertTrue(isinstance(result, cacheprop.CacheProperty))
        mock_property.assert_called_once_with(result)
        self.assertEqual(result.func, func)
        self.assertEqual(result.prop, 'func')
        self.assertEqual(result.cache_attr, '_func')
        self.assertEqual(result.attrs, {})
        self.assertEqual(result.base('spam'), 'spam')

    @mock.patch.object(builtins, 'property', side_effect=lambda x: x)
    def test_with_func_attrs(self, mock_property):
        def func():
            pass

        result = cacheprop.cached_property(func, 'a', 'b', 'c')

        self.assertTrue(isinstance(result, cacheprop.CacheProperty))
        mock_property.assert_called_once_with(result)
        self.assertEqual(result.func, func)
        self.assertEqual(result.prop, 'func')
        self.assertEqual(result.cache_attr, '_func')
        self.assertEqual(len(result.attrs), 3)
        for attr, getter in result.attrs.items():
            self.assertTrue(attr in 'abc')
            self.assertEqual(getter(mock.Mock(**{attr: 'spam'})), 'spam')
        self.assertEqual(result.base('spam'), 'spam')
