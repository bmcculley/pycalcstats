##  Module statistics.py
##
##  Copyright (c) 2013 Steven D'Aprano.
##
##  Permission is hereby granted, free of charge, to any person obtaining
##  a copy of this software and associated documentation files (the
##  "Software"), to deal in the Software without restriction, including
##  without limitation the rights to use, copy, modify, merge, publish,
##  distribute, sublicense, and/or sell copies of the Software, and to
##  permit persons to whom the Software is furnished to do so, subject to
##  the following conditions:
##
##  The above copyright notice and this permission notice shall be
##  included in all copies or substantial portions of the Software.
##
##  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
##  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
##  MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
##  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
##  CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
##  TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
##  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
Statistics module for Python 3.3 and better.

Calculate statistics of data.
This module provides the following functions and classes:

Summary:

==================  =============================================
Function            Description
==================  =============================================
mean                Arithmetic mean (average) of data.
median              Median (middle value) of data.
mode                Mode (most common value) of data.
pstdev              Population standard deviation of data.
pvariance           Population variance of data.
StatisticsError     Exception for statistics errors.
stdev               Sample standard deviation of data.
sum                 High-precision sum of numeric data.
variance            Sample variance of data.
==================  =============================================


Examples
--------

>>> mean([-1.0, 2.5, 3.25, 5.75])
2.625
>>> stdev([2.5, 3.25, 5.5, 11.25, 11.75])  #doctest: +ELLIPSIS
4.38961843444...


Calculate the standard median of discrete data:

>>> median([2, 3, 4, 5])
3.5


Calculate the median of data grouped into class intervals centred on the
data values provided. E.g. if your data points are rounded to the nearest
whole number:

>>> median.grouped([2, 2, 3, 3, 3, 4])  #doctest: +ELLIPSIS
2.8333333333...

This should be interpreted in this way: you have two data points in the class
interval 1.5-2.5, three data points in the class interval 2.5-3.5, and one in
the class interval 3.5-4.5. The median of these data points is 2.8333...

"""

# Module metadata.
__version__ = "0.1a"
__date__ = "2013-07-31"
__author__ = "Steven D'Aprano"
__author_email__ = "steve+python@pearwood.info"


__all__ = [ 'add_partial', 'sum', 'StatisticsError',
            'pstdev', 'pvariance', 'stdev', 'variance',
            'mean', 'median', 'mode',
          ]


import collections
import math
import numbers
import operator
from builtins import sum as _sum


# === Exceptions ===

class StatisticsError(ValueError):
    pass


# === Public utilities ===

def sum(data, start=0):
    """sum(data [, start]) -> value

    Return a high-precision sum of the given numeric data. If optional
    argument ``start`` is given, it is added to the total. If ``data`` is
    empty, ``start`` (defaulting to 0) is returned.


    Examples
    --------

    >>> sum([3, 2.25, 4.5, -0.5, 1.0], 0.75)
    11.0

    Float sums are calculated using high-precision floating point arithmetic
    that can avoid some sources of round-off error:

    >>> sum([1e50, 1, -1e50] * 1000)  # Built-in sum returns zero.
    1000.0

    Fractions and Decimals are also supported:

    >>> from fractions import Fraction as F
    >>> sum([F(2, 3), F(7, 5), F(1, 4), F(5, 6)])
    Fraction(63, 20)

    Decimal sums honour the context:

    >>> import decimal
    >>> D = decimal.Decimal
    >>> data = [D("0.1375"), D("0.2108"), D("0.3061"), D("0.0419")]
    >>> sum(data)
    Decimal('0.6963')
    >>> with decimal.localcontext(
    ...         decimal.Context(prec=2, rounding=decimal.ROUND_DOWN)):
    ...     sum(data)
    Decimal('0.68')


    Limitations
    -----------

    ``sum`` supports mixed arithmetic with the following limitations:

    - mixing Fractions and Decimals raises TypeError;
    - mixing floats with either Fractions or Decimals coerces to float,
      which may lose precision;
    - complex numbers are not supported.

    These limitations may change without notice in future versions.

    """
    if not isinstance(start, numbers.Number):
        raise TypeError('sum only accepts numbers')
    total = start
    data = iter(data)
    x = None
    if not isinstance(total, float):
        # Non-float sum. If we find a float, we exit this loop and continue
        # with the float code below. Until that happens, we keep adding.
        for x in data:
            if isinstance(x, float):
                total = float(total)
                break
            total += x
        else:
            # No break, so we're done.
            return total
    # High-precision float sum.
    assert isinstance(total, float)
    partials = []
    add_partial(total, partials)
    if x is not None:
        add_partial(x, partials)
    for x in data:
        try:
            # Don't call float() directly, as that converts strings and we
            # don't want that. Also, like all dunder methods, we should call
            # __float__ on the class, not the instance.
            x = type(x).__float__(x)
        except OverflowError:
            x = float('inf') if x > 0 else float('-inf')
        add_partial(x, partials)
    return _sum(partials)


# === Private utilities ===

# Thanks to Raymond Hettinger for his recipe:
# http://code.activestate.com/recipes/393090/
def add_partial(x, partials):
    """Helper function for full-precision summation of binary floats.

    Add float x in place to the list partials, keeping the sum exact with no
    rounding error.


    Arguments
    ---------

    x
        Must be a float.

    partials
        A list containing the partial sums.


    Description
    -----------

    Initialise partials to be an empty list. Then for each float value ``x``
    you wish to add, call ``add_partial(x, partials)``.

    When you are done, call the built-in ``sum(partials)`` to round the
    result to the standard float precision.

    If any x is not a float, or partials is not initialised to an empty
    list, results are undefined.


    Examples
    --------

    >>> partials = []
    >>> for x in (0.125, 1e100, 1e-50, 0.125, 1e100):
    ...     add_partial(x, partials)
    >>> partials
    [0.0, 1e-50, 0.25, 2e+100]

    """
    # Keep these as assertions so they can be optimized away.
    assert isinstance(x, float) and isinstance(partials, list)
    if not partials:
        partials.append(0.0)  # Holder for NAN/INF values.
    if not math.isfinite(x):
        partials[0] += x
        return
    # Rounded x+y stored in hi with the round-off stored in lo.  Together
    # hi+lo are exactly equal to x+y.  The inner loop applies hi/lo summation
    # to each partial so that the list of partial sums remains exact.
    # Depends on IEEE-754 arithmetic guarantees.  See proof of correctness at:
    # www-2.cs.cmu.edu/afs/cs/project/quake/public/papers/robust-arithmetic.ps
    i = 1
    for y in partials[1:]:
        if abs(x) < abs(y):
            x, y = y, x
        hi = x + y
        lo = y - (hi - x)
        if lo:
            partials[i] = lo
            i += 1
        x = hi
    assert i > 0
    partials[i:] = [x]


def _attach_to(target):
    """Attach the decorated function to target.

    >>> def f(): pass
    >>>
    >>> @_attach_to(f)
    ... def g(): pass
    >>>
    >>> f.g is g
    True

    """
    def decorator(func):
        setattr(target, func.__name__, func)
        return func
    return decorator


# === Measures of central tendency (averages) ===

def mean(data):
    """mean(data) -> arithmetic mean of data

    Return the sample arithmetic mean of ``data``, a sequence or iterator
    of real-valued numbers.

    The arithmetic mean is the sum of the data divided by the number of
    data points. It is commonly called "the average", although it is only
    one of many different mathematical averages. It is a measure of the
    central location of the data.


    Examples
    --------

    >>> mean([1, 2, 3, 4, 4])
    2.8

    >>> from fractions import Fraction as F
    >>> mean([F(3, 7), F(1, 21), F(5, 3), F(1, 3)])
    Fraction(13, 21)

    >>> from decimal import Decimal as D
    >>> mean([D("0.5"), D("0.75"), D("0.625"), D("0.375")])
    Decimal('0.5625')


    Errors
    ------

    If ``data`` is empty, StatisticsError will be raised.


    Additional Information
    ----------------------

    The mean is strongly effected by outliers and is not a robust estimator
    for central location: the mean is not necessarily a typical example of
    the data points. For a more robust, although less efficient, measures
    of central location, see ``median`` and ``mode``.

    The sample mean gives an unbiased estimate of the true population mean,
    which means that on average, ``mean(sample)`` will equal the mean of
    the entire population. If you call ``mean`` with the entire population,
    the result returned is the population mean \N{GREEK SMALL LETTER MU}.
    """
    if iter(data) is data:
        data = list(data)
    n = len(data)
    if n < 1:
        raise StatisticsError('mean requires at least one data point')
    return sum(data)/n


# FIXME: investigate ways to calculate medians without sorting?
def median(data):
    """Return the median (middle value) of numeric data.

    The median is a robust measure of central location, and is less affected
    by the presence of outliers in your data.

    This uses the "mean-of-middle-two" method of calculating the median. When
    the number of data points is odd, the middle data point is returned:

    >>> median([1, 3, 5])
    3

    When the number of data points is even, the median is interpolated by
    taking the average of the two middle values:

    >>> median([1, 3, 5, 7])
    4.0

    This is best suited when your data is discrete, and you don't mind that
    the median may not be an actual data point. Three other methods for
    calculating median are provided as methods on the ``median`` function:

        * median.low
        * median.high
        * median.grouped
        
    See individual methods for details.
    """
    # If you think that having four definitions of median is annoying, you
    # ought to see the FIFTEEN definitions for quartiles!
    data = sorted(data)
    n = len(data)
    if n == 0:
        raise StatisticsError("no median for empty data")
    if n%2 == 1:
        return data[n//2]
    else:
        i = n//2
        return (data[i - 1] + data[i])/2


@_attach_to(median)
def low(data):
    """Return the low median of numeric data.

    The low median is always a member of the data set. When the number
    of data points is odd, the middle value is returned. When it is
    even, the smaller of the two middle values is returned.

    >>> median.low([1, 3, 5])
    3
    >>> median.low([1, 3, 5, 7])
    3

    Use the low median when your data are discrete and you prefer the median
    to be an actual data point rather than interpolated.
    """
    data = sorted(data)
    n = len(data)
    if n == 0:
        raise StatisticsError("no median for empty data")
    if n%2 == 1:
        return data[n//2]
    else:
        return data[n//2 - 1]


@_attach_to(median)
def high(data):
    """Return the high median of data.

    The high median is always a member of the data set. When the number of
    data points is odd, the middle value is returned. When it is even, the
    larger of the two middle values is returned.

    >>> median.high([1, 3, 5])
    3
    >>> median.high([1, 3, 5, 7])
    5

    Use the high median when your data are discrete and you prefer the median
    to be an actual data point rather than interpolated.
    """
    data = sorted(data)
    n = len(data)
    if n == 0:
        raise StatisticsError("no median for empty data")
    return data[n//2]


@_attach_to(median)
def grouped(data, interval=1):
    """"Return the 50th percentile (median) of grouped continuous data.

    >>> median.grouped([1, 2, 2, 3, 4, 4, 4, 4, 4, 5])
    3.7
    >>> median.grouped([52, 52, 53, 54])
    52.5

    This calculates the median as the 50th percentile, and should be
    used when your data is continuous and grouped. In the above example,
    the values 1, 2, 3, etc. actually represent the midpoint of classes
    0.5-1.5, 1.5-2.5, 2.5-3.5, etc. The middle value falls somewhere in
    class 3.5-4.5, and interpolation is used to estimate it.

    Optional argument ``interval`` represents the class interval, and
    defaults to 1. Changing the class interval naturall will change the
    interpolated 50th percentile value:

    >>> median.grouped([1, 3, 3, 5, 7], interval=1)
    3.25
    >>> median.grouped([1, 3, 3, 5, 7], interval=2)
    3.5

    This function does not check whether the data points are at least
    ``interval`` apart.
    """
    # References:
    # http://www.ualberta.ca/~opscan/median.html
    # https://mail.gnome.org/archives/gnumeric-list/2011-April/msg00018.html
    # https://projects.gnome.org/gnumeric/doc/gnumeric-function-SSMEDIAN.shtml
    data = sorted(data)
    n = len(data)
    if n == 0:
        raise StatisticsError("no median for empty data")
    elif n == 1:
        return data[0]
    # Find the value at the midpoint. Remember this corresponds to the
    # centre of the class interval.
    x = data[n//2]
    for obj in (x, interval):
        if isinstance(obj, (str, bytes)):
            raise TypeError('expected number but got %r' % obj)
    try:
        L = x - interval/2  # The lower limit of the median interval.
    except TypeError:
        # Mixed type. For now we just coerce to float.
        L = float(x) - float(interval)/2
    cf = data.index(x)  # Number of values below the median interval.
    # FIXME The following line could be more efficient for big lists.
    f = data.count(x)  # Number of data points in the median interval.
    return L + interval*(n/2 - cf)/f

del low, high, grouped


def mode(data, max_modes=1):
    """mode(data [, max_modes]) -> mode(s)

    Return the most common data point, or points, from discrete data. The mode
    (when it exists) is the most typical value, and is a robust measure of
    central location.


    Arguments
    ---------

    data
        Non-empty iterable of data points, not necessarily numeric.

    max_modes
        The maximum number of modes to return. Defaults to 1. Passing 0 or
        None as ``max_modes`` will allow an unlimited number of modes.


    Examples
    --------

    ``mode`` assumes discrete data, and by default returns a single value.
    This is the standard treatment of the mode as commonly taught in schools:

    >>> mode([1, 1, 2, 3, 3, 3, 3, 4])
    3

    This also works with nominal (non-numeric) data:

    >>> mode(["red", "blue", "blue", "red", "green", "red", "red"])
    'red'


    If you suspect that your data has more than one mode, pass a positive
    int as the ``max_mode`` argument, and up to that many modes will be
    returned as a list. In this example, the data has two modes, both of which
    have a frequency of three:

    >>> mode([5, 3, 2, 1, 5, 4, 2, 2, 5], max_modes=2)
    [2, 5]


    If you pass 0 or None as ``max_modes``, an unlimited number of modes may
    be returned.


    Errors
    ------

    If your data is empty, or if it has more modes than you specified as
    ``max_modes`` (default of 1), then ``mode`` will raise StatisticsError.
    """
    # Generate a table of sorted (value, frequency) pairs.
    if data is None:
        raise TypeError('None is not iterable')
    table = collections.Counter(data).most_common()
    if not table:
        raise StatisticsError('empty data has no mode')
    # Extract the modes (highest frequency).
    maxfreq = table[0][1]
    for i in range(1, len(table)):
        if table[i][1] != maxfreq:
            table = table[:i]
            break
    if max_modes and len(table) > max_modes:
        raise StatisticsError('got too many modes: %d' % len(table))
    if max_modes == 1:
        assert len(table) == 1
        return table[0][0]
    return [t[0] for t in table]


# === Measures of spread ===

# See http://mathworld.wolfram.com/Variance.html
#     http://mathworld.wolfram.com/SampleVariance.html
#     http://en.wikipedia.org/wiki/Algorithms_for_calculating_variance
#
# Under no circumstances use the so-called "computational formula for
# variance", as that is only suitable for hand calculations with a small
# amount of low-precision data. It has terrible numeric properties.
#
# See a comparison of three computational methods here:
# http://www.johndcook.com/blog/2008/09/26/comparing-three-methods-of-computing-standard-deviation/

def _ss(data, c=None):
    """Return sum of square deviations of sequence data.

    If ``c`` is None, deviations are calculated from the mean. Otherwise,
    deviations are calculated from ``c``. Use the second case with care, as
    it can lead to garbage results.
    """
    if c is None:
        c = mean(data)
    ss = sum((x-c)**2 for x in data)
    # The following sum should mathematically equal zero, but due to rounding
    # error may not.
    ss -= sum((x-c) for x in data)**2/len(data)
    assert not ss < 0, 'negative sum of square deviations: %f' % ss
    return ss


def variance(data, center=None):
    """variance(data [, center]) -> sample variance of numeric data

    Return the sample variance of ``data``, a sequence of real-valued numbers.

    Variance is a measure of the variability (spread or dispersion) of
    data. A large variance indicates that the data is spread out; a small
    variance indicates it is clustered closely around the central location.

    Use this function when your data is a sample. If your data is the entire
    population, you should use ``pvariance`` instead.


    Arguments
    ---------

    data
        sequence of numeric (non-complex) data with at least two values.

    center
        Central location from which to measure variance (optional). If missing
        or None (the default), the mean is used as that central location.


    Examples
    --------

    >>> data = [2.75, 1.75, 1.25, 0.25, 0.5, 1.25, 3.5]
    >>> variance(data)
    1.3720238095238095

    If you have already calculated the mean of your data, you can pass it as
    the optional second argument to avoid recalculating it:

    >>> m = mean(data)
    >>> variance(data, m)
    1.3720238095238095

        .. CAUTION:: Using arbitrary values for ``center`` may lead to invalid
           or impossible results.


    Decimals and Fractions are supported:

    >>> from decimal import Decimal as D
    >>> variance([D("27.5"), D("30.25"), D("30.25"), D("34.5"), D("41.75")])
    Decimal('31.01875')

    >>> from fractions import Fraction as F
    >>> variance([F(1, 6), F(1, 2), F(5, 3)])
    Fraction(67, 108)


    Additional Information
    ----------------------

    This is the unbiased sample variance s\N{SUPERSCRIPT TWO} with Bessel's
    correction, also known as variance with N-1 degrees of freedom. If you
    know the true population mean \N{GREEK SMALL LETTER MU} you should use
    the ``pvariance`` function instead.
    """
    if iter(data) is data:
        data = list(data)
    n = len(data)
    if n < 2:
        raise StatsError('variance requires at least two data points')
    ss = _ss(data, center)
    return ss/(n-1)


def pvariance(data, center=None):
    """pvariance(data [, center]) -> population variance of numeric data

    Return the population variance of ``data``, a sequence of real-valued
    numbers.

    Variance is a measure of the variability (spread or dispersion) of
    data. A large variance indicates that the data is spread out; a small
    variance indicates it is clustered closely around the central location.

    If your data represents the entire population, you should use this
    function; otherwise you should normally use ``variance`` instead.


    Arguments
    ---------

    data
        non-empty sequence of numeric (non-complex) data.

    center
        Central location from which to measure variance (optional). If missing
        or None (the default), the mean is used as that central location.


    Examples
    --------

    >>> data = [0.0, 0.25, 0.25, 1.25, 1.5, 1.75, 2.75, 3.25]
    >>> pvariance(data)
    1.25

    If you have already calculated the mean of your data, you can pass it as
    the optional second argument to avoid recalculating it:

    >>> m = mean(data)
    >>> pvariance(data, m)
    1.25

        .. CAUTION:: Using arbitrary values for ``center`` may lead to invalid
           or impossible results.


    Decimals and Fractions are supported:

    >>> from decimal import Decimal as D
    >>> pvariance([D("27.5"), D("30.25"), D("30.25"), D("34.5"), D("41.75")])
    Decimal('24.8150')

    >>> from fractions import Fraction as F
    >>> pvariance([F(1, 4), F(5, 4), F(1, 2)])
    Fraction(13, 72)

    Additional Information
    ----------------------

    When called with the entire population, this gives the population variance
    \N{GREEK SMALL LETTER SIGMA}\N{SUPERSCRIPT TWO}. When called on a sample
    instead, this is the biased sample variance s\N{SUPERSCRIPT TWO}, also
    known as variance with N degrees of freedom.

    If you somehow know the true population mean \N{GREEK SMALL LETTER MU},
    you should use this function to calculate the sample variance, giving the
    known population mean as the second argument. In that case, the result
    will be an unbiased estimate of the population variance.
    """
    if iter(data) is data:
        data = list(data)
    n = len(data)
    if n < 1:
        raise StatsError('pvariance requires at least one data point')
    ss = _ss(data, center)
    return ss/n


def stdev(data, center=None):
    """stdev(data [, center]) -> sample standard deviation of numeric data

    Return the square root of the sample variance. See ``variance`` for
    arguments and other details.

    >>> stdev([1.5, 2.5, 2.5, 2.75, 3.25, 4.75])
    1.0810874155219827

    """
    var = variance(data, center)
    try:
        return var.sqrt()
    except AttributeError:
        return math.sqrt(var)


def pstdev(data, center=None):
    """pstdev(data [, center]) -> population standard deviation of numeric data

    Return the square root of the population variance. See ``pvariance`` for
    arguments and other details.

    >>> pstdev([1.5, 2.5, 2.5, 2.75, 3.25, 4.75])
    0.986893273527251

    """
    var = pvariance(data, center)
    try:
        return var.sqrt()
    except AttributeError:
        return math.sqrt(var)


