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

import functools
import inspect
import operator

from fstree import utils


class CacheProperty(object):
    """
    Represent a cached property.  A cached property is a property
    where the getter is called only when needed, and that value is
    then cached for later usage.  Cache control data is stored to
    allow the cached value to be invalidated if given attributes or
    properties of the object are updated.
    """

    def __init__(self, func, attrs, base):
        """
        Initialize a ``CachedProperty`` object.

        :param func: The function to call to generate the value to be
                     cached.
        :param attrs: A sequence of attributes of the object obtained
                      by calling ``base``; the values of these
                      attributes must match in order for the cached
                      value to be used.
        :param base: A callable used to obtain a subordinate object
                     from the given object.  All attributes in
                     ``attrs`` will be interpreted as attributes on
                     the object returned by this callable.
        """

        self.func = func
        self.prop = func.__name__
        self.cache_attr = '_%s' % func.__name__
        self.attrs = dict((ch, operator.attrgetter(ch)) for ch in attrs)
        self.base = base

    def __call__(self, obj):
        """
        Obtain the property value.  The cached value will be stored in
        the name of the property, prefixed by an underscore ('_').

        :param obj: The object from which to extract the value.

        :returns: The value.
        """

        # Make sure the object has cache control storage
        try:
            cache_ctrl = obj.__cache_control__
        except AttributeError:
            cache_ctrl = {}
            obj.__cache_control__ = cache_ctrl

        # Get the value
        value = getattr(obj, self.cache_attr, utils.unset)

        # Get the expected value of the cache
        base = self.base(obj)
        expected_ctrl = dict((attr, getter(base))
                             for attr, getter in self.attrs.items())

        # Update the value and the cache control
        if value is utils.unset or cache_ctrl.get(self.prop) != expected_ctrl:
            value = self.func(obj)
            setattr(obj, self.cache_attr, value)
            cache_ctrl[self.prop] = expected_ctrl

        return value


def cached_property(*args, **kwargs):
    """
    Decorator used to mark a "cached" property.  Cached properties are
    properties that are more expensive to compute the first time, but
    which can be cached.  If used without arguments, the property
    value is cached indefinitely, but positional arguments are
    interpreted as attribute names to be used in cache control.  These
    attributes will be obtained from the object the property is
    associated with, unless the ``base`` keyword argument is provided;
    that argument is interpreted as an attribute of the object, and
    the attributes listed as positional arguments will be expected to
    be attributes of that base object.
    """

    # Default base to get
    base = lambda x: x

    # Actual function decorator
    def decorator(func):
        wrapper = CacheProperty(func, args, base)
        functools.update_wrapper(wrapper, func)
        return property(wrapper)

    # First, process the 'base' keyword argument
    if 'base' in kwargs:
        base = operator.attrgetter(kwargs.pop('base'))

    # Next, process the positional arguments, looking for the function
    func = None
    if args and callable(args[0]):
        func = args[0]
        args = args[1:]

    # Now return the decorator or the decorated function
    if func is None:
        return decorator
    return decorator(func)
