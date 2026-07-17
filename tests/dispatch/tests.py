import gc
import logging
import sys
import weakref
from types import TracebackType
from unittest import mock

from django.dispatch import Signal, receiver
from django.test import SimpleTestCase
from django.test.utils import override_settings

if hasattr(sys, 'pypy_version_info'):
    def garbage_collect():
        # Collecting weakreferences can take two collections on PyPy.
        gc.collect()
        gc.collect()
else:
    def garbage_collect():
        gc.collect()


def receiver_1_arg(val, **kwargs):
    return val


class Callable:
    def __call__(self, val, **kwargs):
        return val

    def a(self, val, **kwargs):
        return val


a_signal = Signal()
b_signal = Signal()
c_signal = Signal()
d_signal = Signal(use_caching=True)


class DispatcherTests(SimpleTestCase):

    def assertTestIsClean(self, signal):
        """Assert that everything has been cleaned up automatically"""
        # Note that dead weakref cleanup happens as side effect of using
        # the signal's receivers through the signals API. So, first do a
        # call to an API method to force cleanup.
        self.assertFalse(signal.has_listeners())
        self.assertEqual(signal.receivers, [])

    @override_settings(DEBUG=True)
    def test_cannot_connect_no_kwargs(self):
        def receiver_no_kwargs(sender):
            pass

        msg = 'Signal receivers must accept keyword arguments (**kwargs).'
        with self.assertRaisesMessage(ValueError, msg):
            a_signal.connect(receiver_no_kwargs)
        self.assertTestIsClean(a_signal)

    @override_settings(DEBUG=True)
    def test_cannot_connect_non_callable(self):
        msg = 'Signal receivers must be callable.'
        with self.assertRaisesMessage(AssertionError, msg):
            a_signal.connect(object())
        self.assertTestIsClean(a_signal)

    def test_send(self):
        a_signal.connect(receiver_1_arg, sender=self)
        result = a_signal.send(sender=self, val='test')
        self.assertEqual(result, [(receiver_1_arg, 'test')])
        a_signal.disconnect(receiver_1_arg, sender=self)
        self.assertTestIsClean(a_signal)

    def test_send_no_receivers(self):
        result = a_signal.send(sender=self, val='test')
        self.assertEqual(result, [])

    def test_send_connected_no_sender(self):
        a_signal.connect(receiver_1_arg)
        result = a_signal.send(sender=self, val='test')
        self.assertEqual(result, [(receiver_1_arg, 'test')])
        a_signal.disconnect(receiver_1_arg)
        self.assertTestIsClean(a_signal)

    def test_send_different_no_sender(self):
        a_signal.connect(receiver_1_arg, sender=object)
        result = a_signal.send(sender=self, val='test')
        self.assertEqual(result, [])
        a_signal.disconnect(receiver_1_arg, sender=object)
        self.assertTestIsClean(a_signal)

    def test_garbage_collected(self):
        a = Callable()
        a_signal.connect(a.a, sender=self)
        del a
        garbage_collect()
        result = a_signal.send(sender=self, val="test")
        self.assertEqual(result, [])
        self.assertTestIsClean(a_signal)

    def test_cached_garbaged_collected(self):
        """
        Make sure signal caching sender receivers don't prevent garbage
        collection of senders.
        """
        class sender:
            pass
        wref = weakref.ref(sender)
        d_signal.connect(receiver_1_arg)
        d_signal.send(sender, val='garbage')
        del sender
        garbage_collect()
        try:
            self.assertIsNone(wref())
        finally:
            # Disconnect after reference check since it flushes the tested cache.
            d_signal.disconnect(receiver_1_arg)

    def test_multiple_registration(self):
        a = Callable()
        a_signal.connect(a)
        a_signal.connect(a)
        a_signal.connect(a)
        a_signal.connect(a)
        a_signal.connect(a)
        a_signal.connect(a)
        result = a_signal.send(sender=self, val="test")
        self.assertEqual(len(result), 1)
        self.assertEqual(len(a_signal.receivers), 1)
        del a
        del result
        garbage_collect()
        self.assertTestIsClean(a_signal)

    def test_uid_registration(self):
        def uid_based_receiver_1(**kwargs):
            pass

        def uid_based_receiver_2(**kwargs):
            pass

        a_signal.connect(uid_based_receiver_1, dispatch_uid="uid")
        a_signal.connect(uid_based_receiver_2, dispatch_uid="uid")
        self.assertEqual(len(a_signal.receivers), 1)
        a_signal.disconnect(dispatch_uid="uid")
        self.assertTestIsClean(a_signal)

    def test_send_robust_success(self):
        a_signal.connect(receiver_1_arg)
        result = a_signal.send_robust(sender=self, val='test')
        self.assertEqual(result, [(receiver_1_arg, 'test')])
        a_signal.disconnect(receiver_1_arg)
        self.assertTestIsClean(a_signal)

    def test_send_robust_no_receivers(self):
        result = a_signal.send_robust(sender=self, val='test')
        self.assertEqual(result, [])

    def test_send_robust_ignored_sender(self):
        a_signal.connect(receiver_1_arg)
        result = a_signal.send_robust(sender=self, val='test')
        self.assertEqual(result, [(receiver_1_arg, 'test')])
        a_signal.disconnect(receiver_1_arg)
        self.assertTestIsClean(a_signal)

    def test_send_robust_fail(self):
        def fails(val, **kwargs):
            raise ValueError('this')
        a_signal.connect(fails)
        result = a_signal.send_robust(sender=self, val="test")
        err = result[0][1]
        self.assertIsInstance(err, ValueError)
        self.assertEqual(err.args, ('this',))
        self.assertTrue(hasattr(err, '__traceback__'))
        self.assertIsInstance(err.__traceback__, TracebackType)
        a_signal.disconnect(fails)
        self.assertTestIsClean(a_signal)

    def test_disconnection(self):
        receiver_1 = Callable()
        receiver_2 = Callable()
        receiver_3 = Callable()
        a_signal.connect(receiver_1)
        a_signal.connect(receiver_2)
        a_signal.connect(receiver_3)
        a_signal.disconnect(receiver_1)
        del receiver_2
        garbage_collect()
        a_signal.disconnect(receiver_3)
        self.assertTestIsClean(a_signal)

    def test_values_returned_by_disconnection(self):
        receiver_1 = Callable()
        receiver_2 = Callable()
        a_signal.connect(receiver_1)
        receiver_1_disconnected = a_signal.disconnect(receiver_1)
        receiver_2_disconnected = a_signal.disconnect(receiver_2)
        self.assertTrue(receiver_1_disconnected)
        self.assertFalse(receiver_2_disconnected)
        self.assertTestIsClean(a_signal)

    def test_has_listeners(self):
        self.assertFalse(a_signal.has_listeners())
        self.assertFalse(a_signal.has_listeners(sender=object()))
        receiver_1 = Callable()
        a_signal.connect(receiver_1)
        self.assertTrue(a_signal.has_listeners())
        self.assertTrue(a_signal.has_listeners(sender=object()))
        a_signal.disconnect(receiver_1)
        self.assertFalse(a_signal.has_listeners())
        self.assertFalse(a_signal.has_listeners(sender=object()))


class SendRobustLoggingContractTests(SimpleTestCase):

    def test_sigrob_001_receiver_exception_logs_at_exception_level_with_exception_info_and_traceback(self):
        """GUID: SIGROB-001 - A handled receiver exception is fully logged."""
        signal = Signal()

        def fails(**kwargs):
            raise ValueError('receiver failure')

        signal.connect(fails)
        with self.assertLogs('django.dispatch', 'ERROR') as cm:
            responses = signal.send_robust(sender=self)

        self.assertEqual(len(cm.records), 1)
        record = cm.records[0]
        self.assertEqual(record.levelno, logging.ERROR)
        self.assertIs(record.exc_info[1], responses[0][1])
        self.assertIsInstance(record.exc_info[2], TracebackType)

    def test_sigrob_004_receiver_exception_log_identifies_failing_receiver(self):
        """GUID: SIGROB-004 - A failure log identifies its receiver."""
        signal = Signal()

        def failing_receiver(**kwargs):
            raise ValueError('receiver failure')

        signal.connect(failing_receiver)
        with self.assertLogs('django.dispatch', 'ERROR') as cm:
            signal.send_robust(sender=self)

        self.assertIn('failing_receiver', cm.records[0].getMessage())

    def test_sigrob_005_multiple_receiver_exceptions_log_distinct_failure_records(self):
        """GUID: SIGROB-005 - Each handled failure has a distinct log record."""
        signal = Signal()

        def failing_receiver_one(**kwargs):
            raise ValueError('first failure')

        def failing_receiver_two(**kwargs):
            raise TypeError('second failure')

        signal.connect(failing_receiver_one)
        signal.connect(failing_receiver_two)
        with self.assertLogs('django.dispatch', 'ERROR') as cm:
            responses = signal.send_robust(sender=self)

        self.assertEqual(len(cm.records), 2)
        for record, (receiver, response) in zip(cm.records, responses):
            self.assertIn(receiver.__name__, record.getMessage())
            self.assertIs(record.exc_info[1], response)
            self.assertIsInstance(record.exc_info[2], TracebackType)

    def test_sigrob_007_successful_receiver_logs_no_receiver_failure_exception(self):
        """GUID: SIGROB-007 - A successful receiver has no failure log."""
        signal = Signal()

        def succeeds(**kwargs):
            return 'success'

        signal.connect(succeeds)
        with mock.patch('django.dispatch.dispatcher.logger.error') as mocked_log:
            responses = signal.send_robust(sender=self)

        self.assertEqual(responses, [(succeeds, 'success')])
        mocked_log.assert_not_called()

    def test_sigrob_008_empty_dispatch_preserves_return_and_logs_no_receiver_failure_exception(self):
        """GUID: SIGROB-008 - An empty dispatch keeps its return and has no failure log."""
        signal = Signal()
        with mock.patch('django.dispatch.dispatcher.logger.error') as mocked_log:
            responses = signal.send_robust(sender=self)

        self.assertEqual(responses, [])
        mocked_log.assert_not_called()


class SendRobustResultContinuityContractTests(SimpleTestCase):

    def test_sigrob_002_logging_failing_receiver_returns_same_exception_object_without_propagating(self):
        """GUID: SIGROB-002 - A handled failure preserves its exception."""
        signal = Signal()
        receiver_exception = ValueError('receiver failure')

        def fails(**kwargs):
            raise receiver_exception

        signal.connect(fails)
        with mock.patch('django.dispatch.dispatcher.logger.error') as mocked_log:
            responses = signal.send_robust(sender=self)

        self.assertEqual(len(responses), 1)
        self.assertIs(responses[0][0], fails)
        self.assertIs(responses[0][1], receiver_exception)
        mocked_log.assert_called_once()
        self.assertIs(mocked_log.call_args.kwargs['exc_info'], receiver_exception)

    def test_sigrob_003_failing_receiver_does_not_prevent_subsequent_receiver_invocation(self):
        """GUID: SIGROB-003 - Dispatch continues after a receiver failure."""
        signal = Signal()
        receiver_calls = []

        def fails(**kwargs):
            receiver_calls.append('fails')
            raise ValueError('receiver failure')

        def succeeds(**kwargs):
            receiver_calls.append('succeeds')
            return 'subsequent response'

        signal.connect(fails)
        signal.connect(succeeds)
        with mock.patch('django.dispatch.dispatcher.logger.error'):
            responses = signal.send_robust(sender=self)

        self.assertEqual(receiver_calls, ['fails', 'succeeds'])
        self.assertEqual(responses[1], (succeeds, 'subsequent response'))

    def test_sigrob_006_mixed_dispatch_preserves_successful_result_in_receiver_sequence_when_another_fails(self):
        """GUID: SIGROB-006 - A failure leaves successful results unchanged."""
        signal = Signal()
        successful_response = object()
        receiver_exception = ValueError('receiver failure')

        def fails(**kwargs):
            raise receiver_exception

        def succeeds(**kwargs):
            return successful_response

        signal.connect(fails)
        signal.connect(succeeds)
        with mock.patch('django.dispatch.dispatcher.logger.error'):
            responses = signal.send_robust(sender=self)

        self.assertEqual([receiver for receiver, response in responses], [fails, succeeds])
        self.assertIs(responses[0][1], receiver_exception)
        self.assertIs(responses[1][1], successful_response)


class ReceiverTestCase(SimpleTestCase):

    def test_receiver_single_signal(self):
        @receiver(a_signal)
        def f(val, **kwargs):
            self.state = val
        self.state = False
        a_signal.send(sender=self, val=True)
        self.assertTrue(self.state)

    def test_receiver_signal_list(self):
        @receiver([a_signal, b_signal, c_signal])
        def f(val, **kwargs):
            self.state.append(val)
        self.state = []
        a_signal.send(sender=self, val='a')
        c_signal.send(sender=self, val='c')
        b_signal.send(sender=self, val='b')
        self.assertIn('a', self.state)
        self.assertIn('b', self.state)
        self.assertIn('c', self.state)
