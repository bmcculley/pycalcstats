##  Module statistics.py
##
##  Copyright (c) 2013 Steven D'Aprano <steve+python@pearwood.info>.
##
##  Licensed under the Apache License, Version 2.0 (the "License");
##  you may not use this file except in compliance with the License.
##  You may obtain a copy of the License at
##
##  http://www.apache.org/licenses/LICENSE-2.0
##
##  Unless required by applicable law or agreed to in writing, software
##  distributed under the License is distributed on an "AS IS" BASIS,
##  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
##  See the License for the specific language governing permissions and
##  limitations under the License.


"""
Basic statistics module.

This module provides functions for calculating statistics of data, including
averages, variance, and standard deviation.



Calculating averages
--------------------

==================  =============================================
Function            Description
==================  =============================================
mean                Arithmetic mean (average) of data.
median              Median (middle value) of data.
median_low          Low median of data.
median_high         High median of data.
median_grouped      Median, or 50th percentile, of grouped data.
mode                Mode (most common value) of data.
==================  =============================================

Calculate the arithmetic mean ("the average") of data:

>>> mean([-1.0, 2.5, 3.25, 5.75])
2.625


Calculate the standard median of discrete data:

>>> median([2, 3, 4, 5])
3.5


Calculate the median, or 50th percentile, of data grouped into class intervals
centred on the data values provided. E.g. if your data points are rounded to
the nearest whole number:

>>> median_grouped([2, 2, 3, 3, 3, 4])  #doctest: +ELLIPSIS
2.8333333333...

This should be interpreted in this way: you have two data points in the class
interval 1.5-2.5, three data points in the class interval 2.5-3.5, and one in
the class interval 3.5-4.5. The median of these data points is 2.8333...


Calculating variability or spread
---------------------------------

==================  =============================================
Function            Description
==================  =============================================
pvariance           Population variance of data.
variance            Sample variance of data.
pstdev              Population standard deviation of data.
stdev               Sample standard deviation of data.
==================  =============================================

Calculate the standard deviation of sample data:

>>> stdev([2.5, 3.25, 5.5, 11.25, 11.75])  #doctest: +ELLIPSIS
4.38961843444...

If you have previously calculated the mean, you can pass it as the optional
second argument to the four "spread" functions to avoid recalculating it:

>>> data = [1, 2, 2, 4, 4, 4, 5, 6]
>>> xbar = mean(data)
>>> pvariance(data, xbar)
2.5


Other functions and classes
---------------------------

==================  =============================================
Function            Description
==================  =============================================
sum                 High-precision sum of numeric data.
StatisticsError     Exception for statistics errors.
==================  =============================================

The built-in sum function can lose precision when dealing with floats. The
``sum`` function in this module is designed to be higher-precision, while
still supporting Fractions and Decimals, but disallowing non-numeric arguments
such as lists, tuples and strings.


"""

__all__ = [ 'sum', 'StatisticsError',
            'pstdev', 'pvariance', 'stdev', 'variance',
            'median',  'median_low', 'median_high', 'median_grouped',
            'mean', 'mode',
          ]


import collections
import math
import numbers
import operator
from builtins import sum as _sum

from fractions import Fraction
from decimal import Decimal


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

    Some sources of round-off error will be avoided:

    >>> sum([1e50, 1, -1e50] * 1000)  # Built-in sum returns zero.
    1000.0

    Fractions and Decimals are also supported:

    >>> from fractions import Fraction as F
    >>> sum([F(2, 3), F(7, 5), F(1, 4), F(5, 6)])
    Fraction(63, 20)

    >>> from decimal import Decimal as D
    >>> data = [D("0.1375"), D("0.2108"), D("0.3061"), D("0.0419")]
    >>> sum(data)
    Decimal('0.6963')

    """
    n, d = _exact_ratio(start)
    T = type(start)
    partials = {d: n}  # map {denominator: sum of numerators}
    # Micro-optimizations.
    coerce_types = _coerce_types
    exact_ratio = _exact_ratio
    partials_get = partials.get
    # Add numerators for each denominator, and track the "current" type.
    for x in data:
        T = _coerce_types(T, type(x))
        n, d = exact_ratio(x)
        partials[d] = partials_get(d, 0) + n
    if None in partials:
        assert issubclass(T, (float, Decimal))
        assert not math.isfinite(partials[None])
        return T(partials[None])
    total = Fraction()
    for d, n in sorted(partials.items()):
        total += Fraction(n, d)
    if issubclass(T, int):
        assert total.denominator == 1
        return T(total.numerator)
    if issubclass(T, Decimal):
        return T(total.numerator)/total.denominator
    return T(total)


# === Private utilities ===

def _exact_ratio(x):
    """Convert Real number x exactly to (numerator, denominator) pair.

    >>> _exact_ratio(0.25)
    (1, 4)

    x is expected to be an int, Fraction, Decimal or float.
    """
    try:
        try:
            # int, Fraction
            return (x.numerator, x.denominator)
        except AttributeError:
            # float
            try:
                return x.as_integer_ratio()
            except AttributeError:
                # Decimal
                try:
                    return _decimal_to_ratio(x)
                except AttributeError:
                    msg = "can't convert type '{}' to numerator/denominator"
                    raise TypeError(msg.format(type(x).__name__)) from None
    except (OverflowError, ValueError):
        # INF or NAN
        if __debug__:
            # Decimal signalling NANs cannot be converted to float :-(
            if isinstance(x, Decimal):
                assert not x.is_finite()
            else:
                assert not math.isfinite(x)
        return (x, None)


# FIXME This is faster than Fraction.from_decimal, but still too slow.
def _decimal_to_ratio(d):
    """Convert Decimal d to exact integer ratio (numerator, denominator).

    >>> from decimal import Decimal
    >>> _decimal_to_ratio(Decimal("2.6"))
    (26, 10)

    """
    sign, digits, exp = d.as_tuple()        
    if exp in ('F', 'n', 'N'):  # INF, NAN, sNAN
        assert not d.is_finite()
        raise ValueError
    num = 0
    for digit in digits:
        num = num*10 + digit
    if sign:
        num = -num
    den = 10**-exp
    return (num, den)


def _coerce_types(T1, T2):
    """Coerce types T1 and T2 to a common type.

    >>> _coerce_types(int, float)
    <class 'float'>

    Coercion is performed according to this table, where "N/A" means
    that a TypeError exception is raised.

    +----------+-----------+-----------+-----------+----------+
    |          | int       | Fraction  | Decimal   | float    |
    +----------+-----------+-----------+-----------+----------+
    | int      | int       | Fraction  | Decimal   | float    |
    | Fraction | Fraction  | Fraction  | N/A       | float    |
    | Decimal  | Decimal   | N/A       | Decimal   | float    |
    | float    | float     | float     | float     | float    |
    +----------+-----------+-----------+-----------+----------+

    Subclasses trump their parent class; two subclasses of the same
    base class will be coerced to the second of the two.

    """
    # Get the common/fast cases out of the way first.
    if T1 is T2: return T1
    if T1 is int: return T2
    if T2 is int: return T1
    # Subclasses trump their parent class.
    if issubclass(T2, T1): return T2
    if issubclass(T1, T2): return T1
    # Floats trump everything else.
    if issubclass(T2, float): return T2
    if issubclass(T1, float): return T1
    # Subclasses of the same base class give priority to the second.
    if T1.__base__ is T2.__base__: return T2
    # Otherwise, just give up.
    raise TypeError('cannot coerce types %r and %r' % (T1, T2))


def _counts(data):
    # Generate a table of sorted (value, frequency) pairs.
    if data is None:
        raise TypeError('None is not iterable')
    table = collections.Counter(data).most_common()
    if not table:
        return table
    # Extract the values with the highest frequency.
    maxfreq = table[0][1]
    for i in range(1, len(table)):
        if table[i][1] != maxfreq:
            table = table[:i]
            break
    return table


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
    the data points. For more robust, although less efficient, measures of
    central location, see ``median`` and ``mode``.

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


# FIXME: investigate ways to calculate medians without sorting? Quickselect?
def median(data):
    """Return the median (middle value) of numeric data.

    The median is a robust measure of central location, and is less affected
    by the presence of outliers in your data. This uses the "mean-of-middle-two"
    method of calculating the median: when the number of data points is odd,
    the middle data point is returned:

    >>> median([1, 3, 5])
    3

    When the number of data points is even, the median is interpolated by
    taking the average of the two middle values:

    >>> median([1, 3, 5, 7])
    4.0

    This is suited for when your data is discrete, and you don't mind that
    the median may not be an actual data point.
    """
    data = sorted(data)
    n = len(data)
    if n == 0:
        raise StatisticsError("no median for empty data")
    if n%2 == 1:
        return data[n//2]
    else:
        i = n//2
        return (data[i - 1] + data[i])/2


def median_low(data):
    """Return the low median of numeric data.

    The low median is always a member of the data set. When the number
    of data points is odd, the middle value is returned. When it is
    even, the smaller of the two middle values is returned.

    >>> median_low([1, 3, 5])
    3
    >>> median_low([1, 3, 5, 7])
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


def median_high(data):
    """Return the high median of data.

    The high median is always a member of the data set. When the number of
    data points is odd, the middle value is returned. When it is even, the
    larger of the two middle values is returned.

    >>> median_high([1, 3, 5])
    3
    >>> median_high([1, 3, 5, 7])
    5

    Use the high median when your data are discrete and you prefer the median
    to be an actual data point rather than interpolated.
    """
    data = sorted(data)
    n = len(data)
    if n == 0:
        raise StatisticsError("no median for empty data")
    return data[n//2]


def median_grouped(data, interval=1):
    """"Return the 50th percentile (median) of grouped continuous data.

    >>> median_grouped([1, 2, 2, 3, 4, 4, 4, 4, 4, 5])
    3.7
    >>> median_grouped([52, 52, 53, 54])
    52.5

    This calculates the median as the 50th percentile, and should be
    used when your data is continuous and grouped. In the above example,
    the values 1, 2, 3, etc. actually represent the midpoint of classes
    0.5-1.5, 1.5-2.5, 2.5-3.5, etc. The middle value falls somewhere in
    class 3.5-4.5, and interpolation is used to estimate it.

    Optional argument ``interval`` represents the class interval, and
    defaults to 1. Changing the class interval naturally will change the
    interpolated 50th percentile value:

    >>> median_grouped([1, 3, 3, 5, 7], interval=1)
    3.25
    >>> median_grouped([1, 3, 3, 5, 7], interval=2)
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


def mode(data):
    """mode(data) -> most common value

    Return the most common data point from discrete data. The mode (when it
    exists) is the most typical value, and is a robust measure of central
    location.


    Arguments
    ---------

    data
        Non-empty iterable of data points, not necessarily numeric.


    Examples
    --------

    ``mode`` assumes discrete data, and returns a single value. This is the
    standard treatment of the mode as commonly taught in schools:

    >>> mode([1, 1, 2, 3, 3, 3, 3, 4])
    3

    This also works with nominal (non-numeric) data:

    >>> mode(["red", "blue", "blue", "red", "green", "red", "red"])
    'red'


    Errors
    ------

    If there is not exactly one most common value, ``mode`` will raise
    StatisticsError.
    """
    # Generate a table of sorted (value, frequency) pairs.
    table = _counts(data)
    if len(table) == 1:
        return table[0][0]
    elif table:
        raise StatisticsError(
                'no unique mode; found %d equally common values' % len(table)
                )
    else:
        raise StatisticsError('no mode for empty data')


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

    If ``c`` is None, the mean is calculated in one pass, and the deviations
    from the mean are calculated in a second pass. Otherwise, deviations are
    calculated from ``c`` as given. Use the second case with care, as it can
    lead to garbage results.
    """
    if c is None:
        c = mean(data)
    ss = sum((x-c)**2 for x in data)
    # The following sum should mathematically equal zero, but due to rounding
    # error may not.
    ss -= sum((x-c) for x in data)**2/len(data)
    assert not ss < 0, 'negative sum of square deviations: %f' % ss
    return ss


def variance(data, xbar=None):
    """variance(data [, xbar]) -> sample variance of numeric data

    Return the sample variance of ``data``, a sequence of real-valued numbers.

    Variance, or second moment about the mean, is a measure of the variability
    (spread or dispersion) of data. A large variance indicates that the data
    is spread out; a small variance indicates it is clustered closely around
    the mean.

    Use this function when your data is a sample from a population. To
    calculate the variance from the entire population, see ``pvariance``.


    Arguments
    ---------

    data
        sequence of numeric (non-complex) data with at least two values.

    xbar
        (Optional) Mean of the sample data. If missing or None (the default),
        the mean is automatically caclulated.


    Examples
    --------

    >>> data = [2.75, 1.75, 1.25, 0.25, 0.5, 1.25, 3.5]
    >>> variance(data)
    1.3720238095238095

    If you have already calculated the mean of your data, you can pass it as
    the optional second argument ``xbar`` to avoid recalculating it:

    >>> m = mean(data)
    >>> variance(data, m)
    1.3720238095238095

        .. CAUTION:: Using arbitrary values for ``xbar`` may lead to invalid
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

    This is the sample variance s\N{SUPERSCRIPT TWO} with Bessel's correction,
    also known as variance with N-1 degrees of freedom. Provided the data
    points are representative (e.g. independent and identically distributed),
    the result will be an unbiased estimate of the population variance.

    If you somehow know the population mean \N{GREEK SMALL LETTER MU} you
    should use it with the ``pvariance`` function to get the sample variance.
    """
    if iter(data) is data:
        data = list(data)
    n = len(data)
    if n < 2:
        raise StatisticsError('variance requires at least two data points')
    ss = _ss(data, xbar)
    return ss/(n-1)


def pvariance(data, mu=None):
    """pvariance(data [, mu]) -> population variance of numeric data

    Return the population variance of ``data``, a sequence of real-valued
    numbers.

    Variance, or second moment about the mean, is a measure of the variability
    (spread or dispersion) of data. A large variance indicates that the data
    is spread out; a small variance indicates it is clustered closely around
    the mean.

    Use this function to calculate the variance from the entire population.
    To estimate the variance from a sample, the ``variance`` function is
    usually a better choice.

    Arguments
    ---------

    data
        non-empty sequence of numeric (non-complex) data.

    mu
        (Optional) Mean of the population from which your data has been taken.
        If ``mu`` is missing or None (the default), the data is presumed to be
        the entire population, and the mean automatically calculated.


    Examples
    --------

    >>> data = [0.0, 0.25, 0.25, 1.25, 1.5, 1.75, 2.75, 3.25]
    >>> pvariance(data)
    1.25

    If you have already calculated the mean of the data, you can pass it as
    the optional second argument to avoid recalculating it:

    >>> mu = mean(data)
    >>> pvariance(data, mu)
    1.25

        .. CAUTION:: Using arbitrary values for ``mu`` may lead to invalid
           or impossible results.

    Decimals and Fractions are supported:

    >>> from decimal import Decimal as D
    >>> pvariance([D("27.5"), D("30.25"), D("30.25"), D("34.5"), D("41.75")])
    Decimal('24.815')

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
    you may use this function to calculate the sample variance, giving the
    known population mean as the second argument. Provided the data points are
    representative (e.g. independent and identically distributed), the result
    will be an unbiased estimate of the population variance.
    """
    if iter(data) is data:
        data = list(data)
    n = len(data)
    if n < 1:
        raise StatisticsError('pvariance requires at least one data point')
    ss = _ss(data, mu)
    return ss/n


def stdev(data, xbar=None):
    """stdev(data [, xbar]) -> sample standard deviation of numeric data

    Return the square root of the sample variance. See ``variance`` for
    arguments and other details.

    >>> stdev([1.5, 2.5, 2.5, 2.75, 3.25, 4.75])
    1.0810874155219827

    """
    var = variance(data, xbar)
    try:
        return var.sqrt()
    except AttributeError:
        return math.sqrt(var)


def pstdev(data, mu=None):
    """pstdev(data [, mu]) -> population standard deviation of numeric data

    Return the square root of the population variance. See ``pvariance`` for
    arguments and other details.

    >>> pstdev([1.5, 2.5, 2.5, 2.75, 3.25, 4.75])
    0.986893273527251

    """
    var = pvariance(data, mu)
    try:
        return var.sqrt()
    except AttributeError:
        return math.sqrt(var)


