#!/usr/bin/env python3
# -*- coding: utf-8 -*-

##  Copyright (c) 2011 Steven D'Aprano.
##  See the file stats/__init__.py for the licence terms for this software.

"""Test suite for the rest of the stats package."""

# Implementation note: many test results have been calculated using a
# HP-48GX calculator. Any reference to "RPL" refers to programs written
# on the HP-48GX.


import collections
import inspect
import itertools
import math
import random
import unittest

import stats
import test_stats

# Modules to test:
import stats.co
import stats.multivar
import stats.order
import stats.univar



# === Mixin classes ===

class DoubleDataFailMixin:
    # Override tests that are based on data with 1 or 2 items.
    def testSingleData(self):
       self.assertRaises(ValueError, self.func, [23])
    def testDoubleData(self):
        self.assertRaises(ValueError, self.func, [23, 42])

    testSingleton = testSingleData


# === Unit tests ===

# -- co module --------------------------------------------------------

class CoGlobalsTest(test_stats.GlobalsTest):
    module = stats.co


class CoFeedTest(unittest.TestCase, test_stats.TestConsumerMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Define a coroutine.
        def counter():
            # Coroutine that counts items sent in.
            c = 0
            _ = (yield None)
            while True:
                c += 1
                _ = (yield c)

        self.func = counter

    def testIsGenerator(self):
        # A bare coroutine without the @coroutine decorator will be seen
        # as a generator, due to the presence of `yield`.
        self.assertTrue(inspect.isgeneratorfunction(self.func))

    def testCoroutine(self):
        # Test the coroutine behaves as expected.
        cr = self.func()
        # Initialise the coroutine.
        _ = cr.send(None)
        self.assertEqual(cr.send("spam"), 1)
        self.assertEqual(cr.send("ham"), 2)
        self.assertEqual(cr.send("eggs"), 3)
        self.assertEqual(cr.send("spam"), 4)

    def testFeed(self):
        # Test the feed() helper behaves as expected.
        cr = self.func()
        _ = cr.send(None)
        it = stats.co.feed(cr, "spam spam spam eggs bacon and spam".split())
        self.assertEqual(next(it), 1)
        self.assertEqual(next(it), 2)
        self.assertEqual(next(it), 3)
        self.assertEqual(next(it), 4)
        self.assertEqual(next(it), 5)
        self.assertEqual(next(it), 6)
        self.assertEqual(next(it), 7)
        self.assertRaises(StopIteration, next, it)
        self.assertRaises(StopIteration, next, it)


class CoSumTest(unittest.TestCase, test_stats.TestConsumerMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.co.sum

    def testAlias(self):
        # stats.co.sum is documented as an alias (otherwise we would have
        # to modify the docstring to hide the fact, and that's a PITA). So
        # test for it here.
        self.assertTrue(self.func is stats.running_sum)

    def testSum(self):
        cr = self.func()
        self.assertEqual(cr.send(3), 3)
        self.assertEqual(cr.send(5), 8)
        self.assertEqual(cr.send(0), 8)
        self.assertEqual(cr.send(-2), 6)
        self.assertEqual(cr.send(0.5), 6.5)
        self.assertEqual(cr.send(2.75), 9.25)

    def testSumStart(self):
        cr = self.func(12)
        self.assertEqual(cr.send(3), 15)
        self.assertEqual(cr.send(5), 20)
        self.assertEqual(cr.send(0), 20)
        self.assertEqual(cr.send(-2), 18)
        self.assertEqual(cr.send(0.5), 18.5)
        self.assertEqual(cr.send(2.75), 21.25)

    def testSumTortureTest(self):
        cr = self.func()
        for i in range(100):
            self.assertEqual(cr.send(1), 2*i+1)
            self.assertEqual(cr.send(1e100), 1e100)
            self.assertEqual(cr.send(1), 1e100)
            self.assertEqual(cr.send(-1e100), 2*i+2)


class CoMeanTest(unittest.TestCase, test_stats.TestConsumerMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.co.mean

    def testMean(self):
        cr = self.func()
        self.assertEqual(cr.send(7), 7.0)
        self.assertEqual(cr.send(3), 5.0)
        self.assertEqual(cr.send(5), 5.0)
        self.assertEqual(cr.send(-5), 2.5)
        self.assertEqual(cr.send(0), 2.0)
        self.assertEqual(cr.send(9.5), 3.25)


class CoEWMATest(unittest.TestCase, test_stats.TestConsumerMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.co.ewma

    def testAverages(self):
        # Test the calculated averages.
        cr = self.func()
        self.assertEqual(cr.send(64), 64.0)
        self.assertEqual(cr.send(32), 48.0)
        self.assertEqual(cr.send(16), 32.0)
        self.assertEqual(cr.send(8), 20.0)
        self.assertEqual(cr.send(4), 12.0)
        self.assertEqual(cr.send(2), 7.0)
        self.assertEqual(cr.send(1), 4.0)

    def testAveragesAlpha(self):
        # Test the calculated averages with a specified alpha.
        cr = self.func(0.75)
        self.assertEqual(cr.send(64), 64.0)
        self.assertEqual(cr.send(32), 40.0)
        self.assertEqual(cr.send(58), 53.5)
        self.assertEqual(cr.send(48), 49.375)

    def testBadAlpha(self):
        # Test behaviour with an invalid alpha.
        for a in (None, 'spam', [1], (2,3), {}):
            self.assertRaises(stats.StatsError, self.func, a)


class CoWelfordTest(unittest.TestCase, test_stats.TestConsumerMixin):
    # Test private _welford function.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.co._welford

    def test_welford(self):
        cr = self.func()
        # Expected results calculated by hand, then confirmed using this
        # RPL program: « Σ+ PVAR NΣ * »
        self.assertEqual(cr.send(2), (1, 0.0))
        self.assertEqual(cr.send(3), (2, 0.5))
        self.assertEqual(cr.send(4), (3, 2.0))
        self.assertEqual(cr.send(5), (4, 5.0))
        self.assertEqual(cr.send(6), (5, 10.0))
        cr = self.func()
        # Here I got lazy, and didn't bother with the hand calculations :)
        self.assertEqual(cr.send(3), (1, 0.0))
        self.assertEqual(cr.send(5), (2, 2.0))
        self.assertEqual(cr.send(4), (3, 2.0))
        self.assertEqual(cr.send(3), (4, 2.75))
        self.assertEqual(cr.send(5), (5, 4.0))
        self.assertEqual(cr.send(4), (6, 4.0))
        t = cr.send(-2)
        t = (t[0], round(t[1], 10))
        self.assertEqual(t, (7, 34.8571428571))


class CoPVarTest(test_stats.NumericTestCase, test_stats.TestConsumerMixin):
    # Test coroutine population variance.
    tol = 2e-7
    rel = 2e-7

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.co.pvariance
        self.data = [2, 3, 5, 1, 3.5]
        self.expected = [0.0, 0.25, 14/9, 2.1875, 1.84]

    def testMain(self):
        cr = self.func()
        for x, expected in zip(self.data, self.expected):
            self.assertApproxEqual(cr.send(x), expected, tol=3e-16, rel=None)

    def testShift(self):
        cr1 = self.func()
        data1 = [random.gauss(3.5, 2.5) for _ in range(50)]
        expected = list(stats.co.feed(cr1, data1))
        cr2 = self.func()
        data2 = [x + 1e9 for x in data1]
        result = list(stats.co.feed(cr2, data2))
        self._compare_lists(result, expected)

    def _compare_lists(self, actual, expected):
        assert len(actual) == len(expected)
        for a,e in zip(actual, expected):
            if math.isnan(a) and math.isnan(e):
                self.assertTrue(True)
            else:
                self.assertApproxEqual(a, e)


class CoPstdevTest(CoPVarTest):
    # Test coroutine population std dev.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.co.pstdev
        self.expected = [math.sqrt(x) for x in self.expected]


class CoVarTest(CoPVarTest):
    # Test coroutine sample variance.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.co.variance
        n = len(self.data)
        self.first = self.data[0]
        del self.data[0]
        self.expected = [x*i/(i-1) for i,x in enumerate(self.expected[1:], 2)]

    def testMain(self):
        cr = self.func()
        x = cr.send(self.first)
        self.assertTrue(math.isnan(x), 'expected nan but got %r' % x)
        for x, expected in zip(self.data, self.expected):
            self.assertApproxEqual(cr.send(x), expected)


class CoStdevTest(CoVarTest):
    # Test coroutine sample std dev.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.co.stdev
        self.expected = [math.sqrt(x) for x in self.expected]


class CoCorrTest(test_stats.NumericTestCase):
    tol = 1e-14

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.co.corr

    def make_data(self, n):
        """Return n pairs of data."""
        def rand():
            return random.uniform(-0.5, 0.5)
        def f(x):
            return (2.3+rand())*x - (0.3+rand())
        domain = range(-17, -17+3*n, 3)
        assert len(domain) == n
        data = [(x, f(x)) for x in domain]
        random.shuffle(data)
        return data

    def get_final_result(self, values):
        cr = self.func()
        for xy in values:
            result = cr.send(xy)
        return result

    def testOrder(self):
        # The order that data is presented shouldn't matter to the
        # final result (although intermediate results may differ).
        xydata = self.make_data(100)
        a = self.get_final_result(xydata)
        random.shuffle(xydata)
        b = self.get_final_result(xydata)
        self.assertApproxEqual(a, b, tol=1e-14)

    def testFirstNan(self):
        # Test that the first result is always a NAN.
        for x in (-11.5, -2, 0, 0.25, 17, 45.95, 1e120):
            for y in (-8.5, -2, 0, 0.5, 31.35, 1e99):
                cr = self.func()
                self.assertTrue(math.isnan(cr.send((x,y))))

    def testPerfectCorrelation(self):
        xydata = [(x, 2.3*x - 0.8) for x in range(-17, 291, 3)]
        random.shuffle(xydata)
        cr = self.func()
        # Skip the equality test on the first value.
        xydata = iter(xydata)
        cr.send(next(xydata))
        for xy in xydata:
            self.assertApproxEqual(cr.send(xy), 1.0, tol=1e-15)

    def testPerfectAntiCorrelation(self):
        xydata = [(x, 273.4 - 3.1*x) for x in range(-22, 654, 7)]
        random.shuffle(xydata)
        cr = self.func()
        # Skip the equality test on the first value.
        xydata = iter(xydata)
        cr.send(next(xydata))
        for xy in xydata:
            self.assertApproxEqual(cr.send(xy), -1.0, tol=1e-15)

    def testPerfectZeroCorrelation(self):
        data = [(x, y) for x in range(1, 10) for y in range(1, 10)]
        result = self.get_final_result(data)
        self.assertApproxEqual(result, 0.0, tol=1e-15)

    def testExact(self):
        xdata = [0, 10, 4, 8, 8]
        ydata = [2, 6, 2, 4, 6]
        result = self.get_final_result(zip(xdata, ydata))
        self.assertEqual(result, 28/32)

    def testDuplicate(self):
        # corr shouldn't change if you duplicate each point.
        # Try first with a high correlation.
        xdata = [random.uniform(-5, 15) for _ in range(15)]
        ydata = [x - 0.5 + random.random() for x in xdata]
        xydata = list(zip(xdata, ydata))
        a = self.get_final_result(xydata)
        b = self.get_final_result(xydata*2)
        self.assertApproxEqual(a, b)
        # And again with a (probably) low correlation.
        ydata = [random.uniform(-5, 15) for _ in range(15)]
        xydata = list(zip(xdata, ydata))
        a = self.get_final_result(xydata)
        b = self.get_final_result(xydata*2)
        self.assertApproxEqual(a, b)

    def testSameCoords(self):
        # Test correlation with (X,X) coordinate pairs.
        data = [random.uniform(-3, 5) for x in range(5)]  # Small list.
        result = self.get_final_result([(x, x) for x in data])
        self.assertApproxEqual(result, 1.0)
        data = [random.uniform(-30, 50) for x in range(100)]  # Medium.
        result = self.get_final_result([(x, x) for x in data])
        self.assertApproxEqual(result, 1.0)
        data = [random.uniform(-3000, 5000) for x in range(100000)]  # Large.
        result = self.get_final_result([(x, x) for x in data])
        self.assertApproxEqual(result, 1.0)

    def generate_stress_data(self, start, end, step):
        """Generate a wide range of X and Y data for stress-testing."""
        xfuncs = (lambda x: x,
                  lambda x: 12345*x + 9876,
                  lambda x: 1e9*x,
                  lambda x: 1e-9*x,
                  lambda x: 1e-7*x + 3,
                  lambda x: 846*x - 423,
                  )
        yfuncs = (lambda y: y,
                  lambda y: 67890*y + 6428,
                  lambda y: 1e9*y,
                  lambda y: 1e-9*y,
                  lambda y: 2342*y - 1171,
                  )
        for i in range(start, end, step):
            xdata = [random.random() for _ in range(i)]
            ydata = [random.random() for _ in range(i)]
            for fx, fy in [(fx,fy) for fx in xfuncs for fy in yfuncs]:
                xs = [fx(x) for x in xdata]
                ys = [fy(y) for y in ydata]
                yield (xs, ys)

    def testStress(self):
        # Stress the corr() function looking for failures of the
        # post-condition -1 <= r <= 1.
        for xdata, ydata in self.generate_stress_data(5, 351, 23):
            cr = self.func()
            xydata = zip(xdata, ydata)
            # Skip the first value, as it is a NAN.
            cr.send(next(xydata))
            for xy in xydata:
                self.assertTrue(-1.0 <= cr.send(xy) <= 1.0)

    def testShift(self):
        # Shifting the data by a constant amount shouldn't change the
        # correlation. In practice, it may introduce some error. We allow
        # for that by increasing the tolerance as the shift gets bigger.
        xydata = self.make_data(100)
        a = self.get_final_result(xydata)
        offsets = [(42, -99), (1.2e6, 4.5e5), (7.8e9, 3.6e9)]
        tolerances = [self.tol, 5e-10, 1e-6]
        for (x0,y0), tol in zip(offsets, tolerances):
            data = [(x+x0, y+y0) for x,y in xydata]
            b = self.get_final_result(data)
            self.assertApproxEqual(a, b, tol=tol)


class CoCalcRTest(unittest.TestCase):
    # Test the _calc_r private function.

    def testNan(self):
        # _calc_r should return a NAN if either of the X or Y args are zero.
        result = stats.co._calc_r(0, 1, 2)
        self.assertTrue(math.isnan(result))
        result = stats.co._calc_r(1, 0, 2)
        self.assertTrue(math.isnan(result))

    def testAssertionFails(self):
        # _calc_r should include an assertion. Engineer a failure of it.
        if __debug__:
            self.assertRaises(AssertionError, stats.co._calc_r, 10, 10, 11)
            self.assertRaises(AssertionError, stats.co._calc_r, 10, 10, -11)

    def testMain(self):
        self.assertEqual(stats.co._calc_r(25, 36, 15), 0.5)



# -- multivar module --------------------------------------------------

class MultivarGlobalsTest(test_stats.GlobalsTest):
    module = stats.multivar


# -- order module -----------------------------------------------------

class OrderGlobalsTest(test_stats.GlobalsTest):
    module = stats.order


class OrderMinmaxTest(unittest.TestCase):
    def testAlias(self):
        # stats.order.minmax is documented as an alias (otherwise we would
        # have to modify the docstring to hide the fact, and that's a PITA).
        # So test for it here.
        self.assertTrue(stats.order.minmax is stats.minmax)


class RoundHalfEvenTest(unittest.TestCase):
    # Test the _round_halfeven private function.

    def test_round(self):
        round_halfeven = stats.order._round_halfeven
        for i in range(10):
            self.assertEqual(round_halfeven(i), i)
            self.assertEqual(round_halfeven(i + 0.001), i)
            self.assertEqual(round_halfeven(i + 0.499), i)
            self.assertEqual(round_halfeven(i + 0.501), i+1)
            self.assertEqual(round_halfeven(i + 0.999), i+1)
        for i in range(0, 20, 2):
            self.assertEqual(round_halfeven(i + 0.5), i)
        for i in range(1, 20, 2):
            self.assertEqual(round_halfeven(i + 0.5), i+1)


class MedianTest(test_stats.NumericTestCase, test_stats.UnivariateMixin):
    # Test median function with the default scheme.

    tol = rel = None  # Default to expect exact equality.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.order.median
        self.data = [1.1, 2.2, 3.3, 4.4, 5.5, 6.6, 7.7, 8.8, 9.9]
        self.expected = 5.5

    def setUp(self):
        random.shuffle(self.data)

    def testCalculationOdd(self):
        assert len(self.data)%2 == 1
        self.assertEqual(self.func(self.data), self.expected)

    def testCalculationEven(self):
        data = [0.0] + self.data
        assert len(data)%2 == 0
        self.assertEqual(self.func(data), 4.95)

    def testBigData(self):
        data = [x + 1e9 for x in self.data]
        expected = self.expected + 1e9
        assert expected != 1e9  # Avoid catastrophic loss of precision.
        self.assertEqual(self.func(data), expected)

    def testSingleton(self):
        for x in [-1.1, 0.0, 1.1, 2.2, 3.3]:
            self.assertEqual(self.func([x]), x)

    def testDoubling(self):
        # Median of [a,b,c...z] should be same as for [a,a,b,b,c,c...z,z].
        # First try with even number of data points.
        data = [random.random() for _ in range(100)]
        assert len(data)%2 == 0
        a = self.func(data)
        b = self.func(data*2)
        self.assertEqual(a, b)
        # Now with odd number.
        data.append(random.random())
        assert len(data)%2 == 1
        a = self.func(data)
        b = self.func(data*2)
        self.assertEqual(a, b)


class MedianExtrasOddNoDups(unittest.TestCase):
    # Extra tests for median involving the schemes.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.median = stats.order.median
        self.schemes = (1, 2, 3, 4)
        self.data = [11, 12, 13, 14, 15]
        self.expected = dict((scheme, 13) for scheme in self.schemes)

    def _validate(self):
        assert len(self.data)%2 == 1
        assert all(self.data.count(x) == 1 for x in self.data)

    def setUp(self):
        self._validate()
        random.shuffle(self.data)

    def testMedianExtras(self):
        for scheme in self.schemes:
            actual = self.median(self.data, scheme)
            self.assertEqual(actual, self.expected[scheme])


class MedianExtrasOddDups(MedianExtrasOddNoDups):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = [11, 12, 13, 13, 14]

    def _validate(self):
        assert len(self.data)%2 == 1


class MedianExtrasEvenNoDups(MedianExtrasOddNoDups):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = [11, 12, 13, 14, 15, 16]
        self.expected = {1: 13.5, 2: 13, 3: 14, 4: 13.5}

    def _validate(self):
        assert len(self.data)%2 == 0
        assert all(self.data.count(x) == 1 for x in self.data)


class MedianExtrasEvenDups1(MedianExtrasOddNoDups):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = [11, 12, 13, 13, 14, 14]
        self.expected = dict((scheme, 13) for scheme in self.schemes)

    def _validate(self):
        assert len(self.data)%2 == 0


class MedianExtrasEvenDups2(MedianExtrasEvenDups1):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = [11, 12, 12, 13, 13, 13]
        self.expected = {1: 12.5, 2: 12, 3: 13, 4: 12.6}


class MidrangeTest(MedianTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.order.midrange

    def testMidrange(self):
        self.assertEqual(self.func([1.0, 2.5]), 1.75)
        self.assertEqual(self.func([1.0, 2.0, 4.0]), 2.5)
        self.assertEqual(self.func([2.0, 4.0, 1.0]), 2.5)
        self.assertEqual(self.func([1.0, 2.5, 3.5, 5.5]), 3.25)
        self.assertEqual(self.func([1.0, 2.5, 3.5, 5.5, 1.5]), 3.25)


class MidhingeTest(DoubleDataFailMixin, MedianTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.order.midhinge

    def testMidhinge(self):
        # True hinges occur for n = 4N+5 items, which is 1 modulo 4.
        # We test midhinge on four test data sets, for 1, 2, 3, 0 modulo 4.
        a = [0.1, 0.4, 1.1, 1.4, 2.1, 2.4, 3.1, 3.4, 4.1, 4.4, 5.1, 5.4, 6.1]
        assert len(a) == 4*2 + 5
        b = a + [6.4]
        c = b + [7.1]
        d = c + [7.4]
        for L in (a, b, c, d):
            random.shuffle(L)
        # self.assertApproxEqual(self.func(a), 2.9, tol=1e-10, rel=None)
        self.assertEqual(self.func(a), (1.4+4.4)/2)  # 2.9 + rounding error.
        self.assertEqual(self.func(b), 3.25)
        self.assertEqual(self.func(c), 3.5)
        self.assertEqual(self.func(d), 3.75)


class TrimeanTest(
        DoubleDataFailMixin,
        test_stats.NumericTestCase,
        test_stats.UnivariateMixin
        ):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.order.trimean

    def generic_sequence_test(self, data, n, expected):
        assert len(data)%4 == n
        random.shuffle(data)
        result = self.func(data)
        self.assertEqual(result, expected)
        data = [x + 1e9 for x in data]
        result = self.func(data)
        self.assertEqual(result, expected+1e9)

    def testSeq0(self):
        data = [1.1, 2.2, 3.3, 4.4, 5.5, 6.6, 7.7, 8.8]
        expected = ((2.2+3.3)/2 + 4.4 + 5.5 + (6.6+7.7)/2)/4
        self.generic_sequence_test(data, 0, expected)

    def testSeq1(self):
        data = [1.1, 2.2, 3.3, 4.4, 5.5, 6.6, 7.7, 8.8, 9.9]
        expected = (3.3 + 5.5*2 + 7.7)/4
        self.generic_sequence_test(data, 1, expected)

    def testSeq2(self):
        data = [0.0, 1.1, 2.2, 3.3, 4.4, 5.5, 6.6, 7.7, 8.8, 9.9]
        expected = (2.2 + 4.4 + 5.5 + 7.7)/4
        self.generic_sequence_test(data, 2, expected)

    def testSeq3(self):
        data = [-1.1, 0.0, 1.1, 2.2, 3.3, 4.4, 5.5, 6.6, 7.7, 8.8, 9.9]
        expected = ((1.1+2.2)/2 + 4.4*2 + (6.6+7.7)/2)/4
        self.generic_sequence_test(data, 3, expected)

    def testIter(self):
        data = [1.1, 3.3, 4.4, 6.6, 7.7, 9.9]
        expected = (3.3 + 4.4 + 6.6 + 7.7)/4
        self.assertEqual(self.func(iter(data)), expected)


class RangeTest(test_stats.NumericTestCase, test_stats.UnivariateMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.order.range

    def testSingleton(self):
        for x in (-3.1, 0.0, 4.2, 1.789e12):
            self.assertEqual(self.func([x]), 0)

    def generate_data_sets(self):
        # Yield 2-tuples of (data, expected range).
        # List arguments:
        yield ([42], 0)
        yield ([1, 5], 4)
        yield ([1.5, 4.5, 9.0], 7.5)
        yield ([5, 5, 5], 0)
        data = list(range(500))
        random.shuffle(data)
        for shift in (0, 0.5, 1234.567, -1000, 1e6, 1e9):
            d = [x + shift for x in data]
            yield (d, 499)
        # Subclass of list:
        class MyList(list):
            pass
        yield (MyList([1, 2, 3, 4, 5, 6]), 5)
        yield (MyList([-1, 0, 1, 2, 3, 4, 5]), 6)
        yield (MyList([-1, -2, -3, -4, -5]), 4)
        # Tuple arguments:
        yield ((7, 2), 5)
        yield ((7, 2, 5, 6), 5)
        yield ((3.25, 7.5, 3.25, 4.2), 4.25)
        # range objects:
        yield (range(11), 10)
        yield (range(11, -1, -1), 11)

    def testSequence(self):
        for data, expected in self.generate_data_sets():
            self.assertEqual(self.func(data), expected)

    def testIterator(self):
        for data, expected in self.generate_data_sets():
            self.assertEqual(self.func(iter(data)), expected)

    def testHasD2(self):
        self.assertTrue(hasattr(self.func, 'd2'))
        self.assertTrue(isinstance(self.func.d2, dict))

    def testInterval(self):
        # Test range with an interval argument.
        self.assertEqual(self.func([1, 5], 0.5), 4.5)
        self.assertEqual(self.func([2, 4, 6, 8], 1), 7)
        self.assertEqual(self.func([-1, 0, 1], 0.01), 2.01)

    def testBadInterval(self):
        exc = (TypeError, ValueError)
        for interval in (None, 'spam', [], {}, object(), len):
            self.assertRaises(exc, self.func, [1, 2, 3], interval)


class IQRTest(
    DoubleDataFailMixin,
    test_stats.NumericTestCase,
    test_stats.UnivariateMixin
    ):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.order.iqr
        self.schemes = [1, 2, 3, 4, 5, 6]

    def testBadScheme(self):
        # Test that a bad scheme raises an exception.
        exc = (KeyError, TypeError)
        for scheme in (-1, 1.5, "spam", object(), {}, [], None):
            self.assertRaises(exc, self.func, [1, 2, 3, 4], scheme)

    def testTriplet(self):
        # Test that data consisting of three items behaves as expected.
        data = [1, 5, 12]
        self.assertEqual(self.func(data, 'inclusive'), 5.5)
        self.assertEqual(self.func(data, 'exclusive'), 11)

    def testCaseInsensitive(self):
        # Test that aliases are case-insensitive.
        data = [1, 2, 3, 6, 9, 12, 18, 22]
        for name, num in stats.order.quartiles.aliases.items():
            expected = self.func(data, num)
            self.assertEqual(self.func(data, name.lower()), expected)
            self.assertEqual(self.func(data, name.upper()), expected)
            self.assertEqual(self.func(data, name.title()), expected)

    def same_result(self, data, scheme):
        """Check that data gives the same result, no matter what
        order it is given in."""
        assert len(data) > 2
        if len(data) <= 7:
            # Test every permutation exhaustively for small amounts of data.
            perms = itertools.permutations(data)
        else:
            # Take a random sample for larger amounts of data.
            data = list(data)
            perms = []
            for _ in range(50):
                random.shuffle(data)
                perms.append(data[:])
        results = [self.func(perm, scheme) for perm in perms]
        assert len(results) > 1
        self.assertTrue(len(set(results)) == 1)

    def testCompareOrder(self):
        # Ensure results don't depend on the order of the input.
        for scheme in self.schemes:
            for size in range(3, 12):  # size % 4 -> 3,0,1,2 ...
                self.same_result(range(size), scheme)


class MAD_Test(test_stats.NumericTestCase, test_stats.UnivariateMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.order.mad

    def testSuppliedMedian(self):
        # Test that pre-calculating the median gives the same result.
        import stats.order
        for data in (range(35), range(-17, 53, 7), range(11, 79, 3)):
            result1 = self.func(data)
            m = stats.order.median(data)
            data = list(data)
            random.shuffle(data)
            result2 = self.func(data, m)
            self.assertEqual(result1, result2)

    def testMain(self):
        data = [-1.25, 0.5, 0.5, 1.75, 3.25, 4.5, 4.5, 6.25, 6.75, 9.75]
        expected = 2.625
        for delta in (0, 100, 1e6, 1e9):
            self.assertEqual(self.func(x+delta for x in data), expected)

    def testHasScaling(self):
        self.assertTrue(hasattr(self.func, 'scaling'))

    def testNoScaling(self):
        # Test alternative ways of spelling no scaling factor.
        data = [random.random()+23 for _ in range(100)]
        expected = self.func(data)
        for scale in (1, None, 'none'):
            self.assertEqual(self.func(data, scale=scale), expected)

    def testScales(self):
        data = [100*random.random()+42 for _ in range(100)]
        expected = self.func(data)
        self.assertEqual(self.func(data, scale='normal'), expected*1.4826)
        self.assertApproxEqual(
            self.func(data, scale='uniform'),
            expected*1.1547, # Documented value in docstring.
            tol=0.0001, rel=None)
        self.assertEqual(self.func(data, scale='uniform'),
            expected*math.sqrt(4/3))  # Exact value.
        for x in (-1.25, 0.0, 1.25, 4.5, 9.75):
            self.assertEqual(self.func(data, scale=x), expected*x)

    def testCaseInsensitiveScaling(self):
        for scale in ('normal', 'uniform', 'none'):
            data = [67*random.random()+19 for _ in range(100)]
            a = self.func(data, scale=scale.lower())
            b = self.func(data, scale=scale.upper())
            c = self.func(data, scale=scale.title())
            self.assertEqual(a, b)
            self.assertEqual(a, c)

    def testSchemeOdd(self):
        # Test scheme argument with odd number of data points.
        data = [23*random.random()+42 for _ in range(55)]
        assert len(data)%2 == 1
        a = self.func(data, scheme=1)
        b = self.func(data, scheme=2)
        c = self.func(data, scheme=3)
        d = self.func(data)
        self.assertEqual(a, b)
        self.assertEqual(a, c)
        self.assertEqual(a, d)

    def testSignEven(self):
        # Test scheme argument with even number of data points.
        data = [0.5, 1.5, 3.25, 4.25, 6.25, 6.75]
        assert len(data)%2 == 0
        self.assertEqual(self.func(data), 2.375)
        self.assertEqual(self.func(data, scheme=1), 2.375)
        self.assertEqual(self.func(data, scheme=2), 1.75)
        self.assertEqual(self.func(data, scheme=3), 2.5)


class FiveNumTest(
    DoubleDataFailMixin,
    test_stats.NumericTestCase,
    test_stats.UnivariateMixin
    ):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.order.fivenum

    def testCompareWithQuartiles(self):
        # Compare results with those from the quartiles function using
        # the 'hinges' scheme.
        quartiles = stats.order.quartiles
        for n in range(3, 25):
            data = list(range(n))
            random.shuffle(data)
            self.assertEqual(self.func(data)[1:-1], quartiles(data, 'hinges'))

    def testCompareWithMinMax(self):
        # Compare results with the min and max.
        for n in range(3, 25):
            data = list(range(n))
            random.shuffle(data)
            t = self.func(data)
            self.assertEqual(t[0], min(data))
            self.assertEqual(t[-1], max(data))

    def testSummary(self):
        # Compare results with those calculated by hand.
        f = self.func
        self.assertEqual(f([0, 1, 2, 3, 4]), (0, 1, 2, 3, 4))
        self.assertEqual(f(range(100, 109)), (100, 102, 104, 106, 108))
        self.assertEqual(f(range(100, 110)), (100, 102, 104.5, 107, 109))
        self.assertEqual(f(range(100, 111)), (100, 102.5, 105, 107.5, 110))
        self.assertEqual(f(range(100, 112)), (100, 102.5, 105.5, 108.5, 111))

    def testFields(self):
        # Test that the summary result has named fields.
        names = ('minimum', 'lower_hinge', 'median', 'upper_hinge', 'maximum')
        t = self.func([1, 3, 5, 7, 9])
        self.assertEqual(t._fields, names)


class QuartileSkewnessTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.order.quartile_skewness

    def testFailure(self):
        # Test that function raises an exception if the arguments are
        # out of order.
        self.assertRaises(ValueError, self.func, 2, 3, 1)
        self.assertRaises(ValueError, self.func, 9, 8, 7)

    def testNan(self):
        # Test that the degenerate case where all three arguments are
        # equal returns NAN.
        self.assertTrue(math.isnan(self.func(1, 1, 1)))
        self.assertTrue(math.isnan(self.func(5, 5, 5)))

    def testSkew(self):
        # Test skew calculations.
        self.assertEqual(self.func(3, 5, 7), 0.0)
        self.assertEqual(self.func(0, 1, 10), 0.8)
        self.assertEqual(self.func(0, 9, 10), -0.8)


class QuartilesDrMathTest(unittest.TestCase):
    # Test quartiles function against results given at the Dr Math page:
    # http://mathforum.org/library/drmath/view/60969.html
    # Q2 values are not checked in this test.
    A = range(1, 9)
    B = range(1, 10)
    C = range(1, 11)
    D = range(1, 12)

    def testInclusive(self):
        f = stats.order._Quartiles.inclusive
        q1, _, q3 = f(self.A)
        self.assertEqual(q1, 2.5)
        self.assertEqual(q3, 6.5)
        q1, _, q3 = f(self.B)
        self.assertEqual(q1, 3.0)
        self.assertEqual(q3, 7.0)
        q1, _, q3 = f(self.C)
        self.assertEqual(q1, 3.0)
        self.assertEqual(q3, 8.0)
        q1, _, q3 = f(self.D)
        self.assertEqual(q1, 3.5)
        self.assertEqual(q3, 8.5)

    def testExclusive(self):
        f = stats.order._Quartiles.exclusive
        q1, _, q3 = f(self.A)
        self.assertEqual(q1, 2.5)
        self.assertEqual(q3, 6.5)
        q1, _, q3 = f(self.B)
        self.assertEqual(q1, 2.5)
        self.assertEqual(q3, 7.5)
        q1, _, q3 = f(self.C)
        self.assertEqual(q1, 3.0)
        self.assertEqual(q3, 8.0)
        q1, _, q3 = f(self.D)
        self.assertEqual(q1, 3.0)
        self.assertEqual(q3, 9.0)

    def testMS(self):
        f = stats.order._Quartiles.ms
        q1, _, q3 = f(self.A)
        self.assertEqual(q1, 2)
        self.assertEqual(q3, 7)
        q1, _, q3 = f(self.B)
        self.assertEqual(q1, 3)
        self.assertEqual(q3, 7)
        q1, _, q3 = f(self.C)
        self.assertEqual(q1, 3)
        self.assertEqual(q3, 8)
        q1, _, q3 = f(self.D)
        self.assertEqual(q1, 3)
        self.assertEqual(q3, 9)

    def testMinitab(self):
        f = stats.order._Quartiles.minitab
        q1, _, q3 = f(self.A)
        self.assertEqual(q1, 2.25)
        self.assertEqual(q3, 6.75)
        q1, _, q3 = f(self.B)
        self.assertEqual(q1, 2.5)
        self.assertEqual(q3, 7.5)
        q1, _, q3 = f(self.C)
        self.assertEqual(q1, 2.75)
        self.assertEqual(q3, 8.25)
        q1, _, q3 = f(self.D)
        self.assertEqual(q1, 3.0)
        self.assertEqual(q3, 9.0)

    def testExcel(self):
        f = stats.order._Quartiles.excel
        q1, _, q3 = f(self.A)
        self.assertEqual(q1, 2.75)
        self.assertEqual(q3, 6.25)
        q1, _, q3 = f(self.B)
        self.assertEqual(q1, 3.0)
        self.assertEqual(q3, 7.0)
        q1, _, q3 = f(self.C)
        self.assertEqual(q1, 3.25)
        self.assertEqual(q3, 7.75)
        q1, _, q3 = f(self.D)
        self.assertEqual(q1, 3.5)
        self.assertEqual(q3, 8.5)


class QuartilesAliasesTest(unittest.TestCase):
    def testAliasesMapping(self):
        # Test that the quartiles function exposes a mapping of aliases.
        self.assertTrue(hasattr(stats.order.quartiles, 'aliases'))
        aliases = stats.order.quartiles.aliases
        self.assertTrue(isinstance(aliases, collections.Mapping))
        self.assertTrue(aliases)

    def testAliasesValues(self):
        # Test that the quartiles function aliases all map to real schemes.
        allowed_schemes = set(stats.order._Quartiles.FUNC_MAP.keys())
        used_schemes = set(stats.order.quartiles.aliases.values())
        self.assertTrue(used_schemes.issubset(allowed_schemes))


class QuartilesTest(
    DoubleDataFailMixin,
    test_stats.UnivariateMixin,
    test_stats.NumericTestCase
    ):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.order.quartiles

    def testBadScheme(self):
        # Test that invalid schemes will fail.
        data = range(20)
        exc = (KeyError, TypeError)
        for scheme in ('', 'spam', 1.5, -1.5, -2):
            self.assertRaises(exc, self.func, data, scheme)

    def testCaseInsensitive(self):
        # Test that string scheme aliases are case-insensitive.
        data = range(20)
        for scheme in self.func.aliases:
            a = self.func(data, scheme.lower())
            b = self.func(data, scheme.upper())
            c = self.func(data, scheme.title())
            self.assertEqual(a, b)
            self.assertEqual(a, c)

    def testInclusive(self):
        # Test the inclusive method of calculating quartiles.
        f = self.func
        scheme = 1
        self.assertEqual(f([0, 1, 2], scheme), (0.5, 1, 1.5))
        self.assertEqual(f([0, 1, 2, 3], scheme), (0.5, 1.5, 2.5))
        self.assertEqual(f([0, 1, 2, 3, 4], scheme), (1, 2, 3))
        self.assertEqual(f([0, 1, 2, 3, 4, 5], scheme), (1, 2.5, 4))
        self.assertEqual(f([0, 1, 2, 3, 4, 5, 6], scheme), (1.5, 3, 4.5))
        self.assertEqual(f(range(1, 9), scheme), (2.5, 4.5, 6.5))
        self.assertEqual(f(range(1, 10), scheme), (3, 5, 7))
        self.assertEqual(f(range(1, 11), scheme), (3, 5.5, 8))
        self.assertEqual(f(range(1, 12), scheme), (3.5, 6, 8.5))
        self.assertEqual(f(range(1, 13), scheme), (3.5, 6.5, 9.5))
        self.assertEqual(f(range(1, 14), scheme), (4, 7, 10))
        self.assertEqual(f(range(1, 15), scheme), (4, 7.5, 11))
        self.assertEqual(f(range(1, 16), scheme), (4.5, 8, 11.5))

    def testExclusive(self):
        # Test the exclusive method of calculating quartiles.
        f = self.func
        scheme = 2
        self.assertEqual(f([0, 1, 2], scheme), (0, 1, 2))
        self.assertEqual(f([0, 1, 2, 3], scheme), (0.5, 1.5, 2.5))
        self.assertEqual(f([0, 1, 2, 3, 4], scheme), (0.5, 2, 3.5))
        self.assertEqual(f([0, 1, 2, 3, 4, 5], scheme), (1, 2.5, 4))
        self.assertEqual(f([0, 1, 2, 3, 4, 5, 6], scheme), (1, 3, 5))
        self.assertEqual(f(range(1, 9), scheme), (2.5, 4.5, 6.5))
        self.assertEqual(f(range(1, 10), scheme), (2.5, 5, 7.5))
        self.assertEqual(f(range(1, 11), scheme), (3, 5.5, 8))
        self.assertEqual(f(range(1, 12), scheme), (3, 6, 9))
        self.assertEqual(f(range(1, 13), scheme), (3.5, 6.5, 9.5))
        self.assertEqual(f(range(1, 14), scheme), (3.5, 7, 10.5))
        self.assertEqual(f(range(1, 15), scheme), (4, 7.5, 11))
        self.assertEqual(f(range(1, 16), scheme), (4, 8, 12))

    def testMS(self):
        f = self.func
        scheme = 3
        self.assertEqual(f(range(3), scheme), (0, 1, 2))
        self.assertEqual(f(range(4), scheme), (0, 1, 3))
        self.assertEqual(f(range(5), scheme), (1, 2, 3))
        self.assertEqual(f(range(6), scheme), (1, 3, 4))
        self.assertEqual(f(range(7), scheme), (1, 3, 5))
        self.assertEqual(f(range(8), scheme), (1, 3, 6))
        self.assertEqual(f(range(9), scheme), (2, 4, 6))
        self.assertEqual(f(range(10), scheme), (2, 5, 7))
        self.assertEqual(f(range(11), scheme), (2, 5, 8))
        self.assertEqual(f(range(12), scheme), (2, 5, 9))

    def testMinitab(self):
        f = self.func
        scheme = 4
        self.assertEqual(f(range(3), scheme), (0, 1, 2))
        self.assertEqual(f(range(4), scheme), (0.25, 1.5, 2.75))
        self.assertEqual(f(range(5), scheme), (0.5, 2, 3.5))
        self.assertEqual(f(range(6), scheme), (0.75, 2.5, 4.25))
        self.assertEqual(f(range(7), scheme), (1, 3, 5))
        self.assertEqual(f(range(8), scheme), (1.25, 3.5, 5.75))
        self.assertEqual(f(range(9), scheme), (1.5, 4, 6.5))
        self.assertEqual(f(range(10), scheme), (1.75, 4.5, 7.25))
        self.assertEqual(f(range(11), scheme), (2, 5, 8))
        self.assertEqual(f(range(12), scheme), (2.25, 5.5, 8.75))

    def testExcel(self):
        f = self.func
        scheme = 5
        # Results generated with OpenOffice.
        self.assertEqual(f(range(3), scheme), (0.5, 1, 1.5))
        self.assertEqual(f(range(4), scheme), (0.75, 1.5, 2.25))
        self.assertEqual(f(range(5), scheme), (1, 2, 3))
        self.assertEqual(f(range(6), scheme), (1.25, 2.5, 3.75))
        self.assertEqual(f(range(7), scheme), (1.5, 3, 4.5))
        self.assertEqual(f(range(8), scheme), (1.75, 3.5, 5.25))
        self.assertEqual(f(range(9), scheme), (2, 4, 6))
        self.assertEqual(f(range(10), scheme), (2.25, 4.5, 6.75))
        self.assertEqual(f(range(11), scheme), (2.5, 5, 7.5))
        self.assertEqual(f(range(12), scheme), (2.75, 5.5, 8.25))
        self.assertEqual(f(range(13), scheme), (3, 6, 9))
        self.assertEqual(f(range(14), scheme), (3.25, 6.5, 9.75))
        self.assertEqual(f(range(15), scheme), (3.5, 7, 10.5))

    def testLangford(self):
        f = self.func
        scheme = 6
        self.assertEqual(f(range(3), scheme), (0, 1, 2))
        self.assertEqual(f(range(4), scheme), (0.5, 1.5, 2.5))
        self.assertEqual(f(range(5), scheme), (1, 2, 3))
        self.assertEqual(f(range(6), scheme), (1, 2.5, 4))
        self.assertEqual(f(range(7), scheme), (1, 3, 5))
        self.assertEqual(f(range(8), scheme), (1.5, 3.5, 5.5))
        self.assertEqual(f(range(9), scheme), (2, 4, 6))
        self.assertEqual(f(range(10), scheme), (2, 4.5, 7))
        self.assertEqual(f(range(11), scheme), (2, 5, 8))
        self.assertEqual(f(range(12), scheme), (2.5, 5.5, 8.5))

    def testBig(self):
        # Test some quartiles results on relatively big sets of data.
        data = list(range(1001, 2001))
        assert len(data) == 1000
        assert len(data)%4 == 0
        random.shuffle(data)
        self.assertEqual(self.func(data, 1), (1250.5, 1500.5, 1750.5))
        self.assertEqual(self.func(data, 2), (1250.5, 1500.5, 1750.5))
        data.append(2001)
        random.shuffle(data)
        self.assertEqual(self.func(data, 1), (1251, 1501, 1751))
        self.assertEqual(self.func(data, 2), (1250.5, 1501, 1751.5))
        data.append(2002)
        random.shuffle(data)
        self.assertEqual(self.func(data, 1), (1251, 1501.5, 1752))
        self.assertEqual(self.func(data, 2), (1251, 1501.5, 1752))
        data.append(2003)
        random.shuffle(data)
        self.assertEqual(self.func(data, 1), (1251.5, 1502, 1752.5))
        self.assertEqual(self.func(data, 2), (1251, 1502, 1753))


class QuantileBehaviourTest(
    test_stats.UnivariateMixin,
    test_stats.NumericTestCase
    ):
    # Behaviour tests for quantile (like test_stats.UnivariateMixin except
    # adds a second required argument).

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.raw_func = stats.order.quantile
        self.func = lambda x: self.raw_func(x, 0.5)

    def testNoArgs(self):
        # Fail if given no arguments.
        self.assertRaises(TypeError, self.raw_func)
        self.assertRaises(TypeError, self.func)

    def testSingleArg(self):
        # Fail if given a single argument.
        self.assertRaises(TypeError, self.raw_func, [1, 2, 3])

    def testSingleData(self):
        # Fail when the first argument has a single data point.
        for x in self.make_random_data(size=1, count=4):
            assert len(x) == 1
            self.assertRaises(ValueError, self.func, x)


class QuantileResultsTest(test_stats.NumericTestCase):
    # Test the results returned by quantile.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.order.quantile

    def testQuantileArgOutOfRange(self):
        # Test that the quantile input arg fails if not 0 <= x < 1.
        data = [1, 2, 3, 4]
        self.assertRaises(ValueError, self.func, data, -0.1)
        self.assertRaises(ValueError, self.func, data, 1.1)

    def testUnsorted(self):
        # quantile function should work on unsorted data.
        data = [3, 4, 2, 1, 0, 5]
        assert data != sorted(data)
        self.assertEqual(self.func(data, 0.1, scheme=1), 0)
        self.assertEqual(self.func(data, 0.9, scheme=1), 5)
        self.assertEqual(self.func(data, 0.1, scheme=7), 0.5)
        self.assertEqual(self.func(data, 0.9, scheme=7), 4.5)

    def testIter(self):
        # quantile function should work on iterator data.
        self.assertEqual(self.func(range(12), 0.3, scheme=1), 3)
        self.assertEqual(self.func(range(12), 0.3, scheme=7), 3.3)
        self.assertEqual(self.func(iter([1, 3, 6, 9]), 0.7, scheme=2), 6)
        self.assertApproxEqual(
            self.func(iter([1, 3, 6, 9]), 0.7, scheme=8), 7.1, rel=1e-15)

    def testUnitInterval(self):
        # Test quantile interpolating between 0 and 1.
        data = [0, 1]
        for f in (0.01, 0.1, 0.2, 0.25, 0.5, 0.55, 0.8, 0.9, 0.99):
            result = self.func(data, f, scheme=7)
            self.assertApproxEqual(result, f, tol=1e-9, rel=None)

    def testLQD(self):
        expected = [1.0, 1.7, 3.9, 6.1, 8.3, 10.5, 12.7, 14.9, 17.1, 19.3, 20.0]
        ps = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        data = range(1, 21)
        for i, p in enumerate(ps):
            result = self.func(data, p, scheme=10)
            self.assertApproxEqual(expected[i], result, tol=1e-12, rel=None)


class CompareParameterizedQuantiles(test_stats.NumericTestCase):
    # Compare Mathematica-style parameterized quantiles with the equivalent.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.order.quantile

    def compareMethods(self, scheme, params):
        fractions = [0.0, 0.01, 0.1, 0.2, 0.25, 0.31, 0.42, 0.5,
                     0.55, 0.62, 0.75, 0.83, 0.9, 0.95, 0.99, 1.0]
        data0 = list(range(2000, 2701, 100))
        assert len(data0)%4 == 0
        data1 = list(range(2000, 2801, 100))
        assert len(data1)%4 == 1
        data2 = list(range(2000, 2901, 100))
        assert len(data2)%4 == 2
        data3 = list(range(2000, 3001, 100))
        assert len(data3)%4 == 3
        for data in (data0, data1, data2, data3):
            name = 'data%d' % (len(data) % 4)
            for p in fractions:
                a = self.func(data, p, scheme=scheme)
                b = self.func(data, p, scheme=params)
                self.assertEqual(a, b,
                "Failed for %s with %s != %s; p=%f" % (name, a, b, p))

    def testR1(self):
        scheme = 1; params = (0, 0, 1, 0)
        self.compareMethods(scheme, params)

    # Note that there is no test for R2, as it is not supported by the
    # Mathematica parameterized quantile algorithm.

    @unittest.skip('test currently broken for unknown reasons')
    def testR3(self):
        scheme = 3; params = (0.5, 0, 0, 0)
        self.compareMethods(scheme, params)

    def testR4(self):
        scheme = 4; params = (0, 0, 0, 1)
        self.compareMethods(scheme, params)

    def testR5(self):
        scheme = 5; params = (0.5, 0, 0, 1)
        self.compareMethods(scheme, params)

    def testR6(self):
        scheme = 6; params = (0, 1, 0, 1)
        self.compareMethods(scheme, params)

    def testR7(self):
        scheme = 7; params = (1, -1, 0, 1)
        self.compareMethods(scheme, params)

    def testR8(self):
        scheme = 8; params = (1/3, 1/3, 0, 1)
        self.compareMethods(scheme, params)

    def testR9(self):
        scheme = 9; params = (3/8, 0.25, 0, 1)
        self.compareMethods(scheme, params)


class QuantilesCompareWithR(test_stats.NumericTestCase):
    # Compare results of calling quantile() against results from R.
    tol = 1e-3
    rel = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.read_data('stats-quantiles.dat')
        self.func = stats.order.quantile

    def read_data(self, filename):
        # Read data from external test data file generated using R.
        # First we have to find our location...
        import os
        import __main__
        location = os.path.split(__main__.__file__)[0]
        # Now add the filename to it.
        location = os.path.join(location, filename)
        # Now read the data from that file.
        expected = {}
        with open(location, 'r') as data:
            for line in data:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if '=' in line:
                    label, items = line.split("=")
                    label = label.strip()
                    if label == 'seq':
                        start, end, step = [int(s) for s in items.split()]
                        end += 1
                        self.data = list(range(start, end, step))
                    elif label == 'p':
                        self.fractiles = [float(s) for s in items.split()]
                else:
                    scheme, results = line.split(":")
                    scheme = int(scheme.strip())
                    assert 1 <= scheme <= 9
                    results = [float(x) for x in results.split()]
                    expected[scheme] = results
        self.expected = expected

    def compare(self, scheme):
        fractiles = self.fractiles
        a = [self.func(self.data, p, scheme=scheme) for p in fractiles]
        b = self.expected[scheme]
        for actual, expected in zip(a, b):
            self.assertApproxEqual(actual, expected)

    def testR1(self):  self.compare(1)
    def testR2(self):  self.compare(2)
    def testR3(self):  self.compare(3)
    def testR4(self):  self.compare(4)
    def testR5(self):  self.compare(5)
    def testR6(self):  self.compare(6)
    def testR7(self):  self.compare(7)
    def testR8(self):  self.compare(8)
    def testR9(self):  self.compare(9)


class DecileBehaviourTest(QuantileBehaviourTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.raw_func = stats.order.decile
        self.func = lambda x: self.raw_func(x, 7)


class PercentileBehaviourTest(QuantileBehaviourTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.raw_func = stats.order.percentile
        self.func = lambda x: self.raw_func(x, 63)


class DecileExactSchemesTest(test_stats.NumericTestCase):
    # Test that certain schemes don't perform any interpolation when the
    # number of data points is exactly the same as fractile size.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.schemes = [1, 3, 4]
        self.func = stats.order.decile
        self.num = 10

    def result_is_exact(self, data, i):
        """Test that no interpolation takes place no matter which scheme
        is used."""
        for scheme in self.schemes:
            actual = self.func(data, i, scheme)
            self.assertEqual(actual, i,
                "expected %d with scheme %d but got %s" % (i, scheme, actual))

    def testExact(self):
        # Test that fractiles are exact if there are exactly self.num items.
        data = range(1, 1 + self.num)
        assert len(data) == self.num
        for i in range(1, 1 + self.num):
            self.result_is_exact(data, i)


class PercentileExactSchemeTest(DecileExactSchemesTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.order.percentile
        self.num = 100


class DecileValueTest(test_stats.NumericTestCase):
    # Test deciles against results (mostly) calculated in R.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.order.decile
        self.data = [101, 105, 116, 117, 129, 134, 137, 142, 150, 153, 164, 178]
        assert len(self.data) != 10

    def setUp(self):
        random.shuffle(self.data)

    def do_test(self, i, scheme, expected):
        actual = self.func(self.data, i, scheme)
        self.assertApproxEqual(actual, expected, tol=1e-3)

    def testLow(self):
        for scheme in range(1, 11):
            self.do_test(0, scheme, 101)

    def testMid(self):
        for scheme in (1, 3, 4):
            self.do_test(5, scheme, 134)
        for scheme in (2, 5, 6, 7, 8, 9, 10):
            self.do_test(5, scheme, 135.5)

    def testHigh(self):
        for scheme in range(1, 11):
            self.do_test(10, scheme, 178)

    def testScheme1(self):
        self.do_test(2, 1, 116)
        self.do_test(8, 1, 153)
        self.do_test(9, 1, 164)

    def testScheme2(self):
        self.do_test(1, 2, 105)
        self.do_test(3, 2, 117)
        self.do_test(9, 2, 164)

    def testScheme3(self):
        self.do_test(2, 3, 105)
        self.do_test(7, 3, 142)

    def testScheme4(self):
        self.do_test(1, 4, 101.8)
        self.do_test(4, 4, 126.6)
        self.do_test(8, 4, 151.8)

    def testScheme5(self):
        self.do_test(1, 5, 103.8)
        self.do_test(3, 5, 118.2)
        self.do_test(6, 5, 140.5)
        self.do_test(7, 5, 149.2)

    def testScheme6(self):
        self.do_test(8, 6, 157.4)

    def testScheme7(self):
        self.do_test(2, 7, 116.2)
        self.do_test(3, 7, 120.6)
        self.do_test(6, 7, 140)

    def testScheme8(self):
        self.do_test(4, 8, 130.333)
        self.do_test(7, 8, 149.733)
        self.do_test(6, 8, 140.667)

    def testScheme9(self):
        self.do_test(4, 9, 130.375)
        self.do_test(9, 9, 169.6)

    def testScheme10(self):
        self.do_test(3, 10, 116.7)
        self.do_test(7, 10, 150.9)


class PercentileValueTest(test_stats.NumericTestCase):
    # Test percentiles against results (mostly) calculated in R.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = stats.order.percentile
        self.data = [103, 109, 113, 121, 127, 131, 142, 143, 154,
                     163, 167, 171, 180, 185, 188, 196]
        assert len(self.data) != 100

    def setUp(self):
        random.shuffle(self.data)

    def do_test(self, i, scheme, expected):
        actual = self.func(self.data, i, scheme)
        self.assertApproxEqual(actual, expected, tol=1e-3)

    def testLow(self):
        for scheme in range(1, 11):
            self.do_test(0, scheme, 103)

    def testMid(self):
        for scheme in (1, 3, 4):
            self.do_test(50, scheme, 143)
        for scheme in (2, 5, 6, 7, 8, 9, 10):
            self.do_test(50, scheme, 148.5)

    def testHigh(self):
        for scheme in range(1, 11):
            self.do_test(100, scheme, 196)



# -- univar module ----------------------------------------------------

class UnivarGlobalsTest(test_stats.GlobalsTest):
    module = stats.univar



# === Run tests ===

def test_main():
    unittest.main()


if __name__ == '__main__':
    test_main()
