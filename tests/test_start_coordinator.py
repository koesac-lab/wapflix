"""R2B.2 controlled callbacks only; no fake worker is shipped in runtime code."""
import threading
import unittest
from tools.start_coordinator import StartCoordinator, CoordinatorError
from tools.start_fence import StartFence, FenceError, AdmissionFailed

class Candidate:
    def __init__(self, events, label):
        self.events = events
        self.label = label
        self.owner = None
        self.confirm = True
        self.fail_publish = False
        self.before_stop = None
    def publish(self, owner):
        self.owner = owner
        self.events.append(('publish', self.label))
        if self.fail_publish:
            raise RuntimeError('partial admission')
    def snapshot(self):
        return {'navigation_id': self.owner, 'label': self.label}
    def stop(self):
        self.events.append(('stop', self.label))
        if self.before_stop:
            self.before_stop()
        return self.confirm

class Factory:
    def __init__(self):
        self.events = []
        self.candidates = []
        self.hook = None
    def prepare(self, spec, ticket):
        self.events.append(('prepare', spec))
        candidate = Candidate(self.events, spec)
        self.candidates.append(candidate)
        if self.hook:
            self.hook(candidate, ticket)
        return candidate

class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.fence = StartFence(clock=lambda: self.now)
        self.factory = Factory()
        self.coordinator = StartCoordinator(self.factory, fence=self.fence, lock_timeout=.2)
        self.client = self.fence.open_client()
    def start(self, revision=1, spec='a', client=None):
        return self.coordinator.start(client or self.client, revision, spec)
    def assertCode(self, code, callback):
        with self.assertRaises((FenceError, CoordinatorError)) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)
    def background(self, callback):
        result = []
        def run():
            try:
                result.append(callback())
            except BaseException as error:
                result.append(error)
        thread = threading.Thread(target=run)
        thread.start()
        return thread, result
    def delayed(self):
        entered, release = threading.Event(), threading.Event()
        def hook(candidate, ticket):
            if candidate.label == 'old':
                entered.set()
                if not release.wait(2):
                    raise TimeoutError('test barrier')
        self.factory.hook = hook
        self.addCleanup(release.set)
        thread, result = self.background(lambda: self.start(spec='old'))
        self.assertTrue(entered.wait(1))
        return release, thread, result
    def finish(self, release, thread, result):
        release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(result), 1)
        return result[0]

    def test_factory_required(self):
        with self.assertRaises(ValueError):
            StartCoordinator(None)
    def test_cancel_before_request(self):
        self.coordinator.cancel(self.client, 1)
        self.assertCode('cancelled_start', self.start)
        self.assertEqual(self.factory.events, [])
    def test_duplicate_active_never_prepares_or_stops(self):
        original = self.start()
        self.assertEqual(self.start(spec='ignored'), original)
        self.assertEqual(self.factory.events, [('prepare', 'a'), ('publish', 'a')])
    def test_replacement_reaps_before_publish(self):
        self.start()
        self.start(2, 'b')
        self.assertEqual(self.factory.events, [('prepare','a'), ('publish','a'), ('prepare','b'), ('stop','a'), ('publish','b')])
    def test_cancel_during_preparation(self):
        release, thread, result = self.delayed()
        self.assertEqual(self.coordinator.cancel(self.client, 1)['cleanup'], 'not_required')
        error = self.finish(release, thread, result)
        self.assertEqual(error.code, 'cancelled_start')
        self.assertNotIn(('publish', 'old'), self.factory.events)
    def test_late_preparation_cannot_replace_newer(self):
        release, thread, result = self.delayed()
        fresh = self.start(2, 'fresh')
        error = self.finish(release, thread, result)
        self.assertEqual(error.code, 'stale_start')
        self.assertEqual(self.fence.snapshot()['active_owner'], fresh['navigation_id'])
        self.assertNotIn(('stop', 'fresh'), self.factory.events)
    def test_newer_client_takeover(self):
        release, thread, result = self.delayed()
        newer = self.fence.open_client()
        self.start(1, 'fresh', newer)
        error = self.finish(release, thread, result)
        self.assertEqual(error.code, 'client_superseded')
    def test_cancel_during_replacement_cleanup(self):
        self.start()
        old = self.factory.candidates[0]
        old.before_stop = lambda: self.fence.cancel(self.client, 2)
        self.assertCode('cancelled_start', lambda: self.start(2, 'b'))
        self.assertIsNone(self.fence.snapshot()['active_owner'])
        self.assertNotIn(('publish','b'), self.factory.events)
    def test_cleanup_failure_blocks_replacement_and_can_retry_cancel(self):
        first = self.start()
        self.factory.candidates[0].confirm = False
        self.assertCode('cleanup_unconfirmed', lambda: self.start(2, 'b'))
        self.assertEqual(self.fence.snapshot()['active_owner'], first['navigation_id'])
        self.assertNotIn(('publish','b'), self.factory.events)
        self.factory.candidates[0].confirm = True
        self.assertEqual(self.coordinator.cancel(self.client, 2)['cleanup'], 'confirmed')
        self.start(3, 'c')
    def test_partial_admission_retains_owner(self):
        self.factory.hook = lambda candidate, ticket: setattr(candidate, 'fail_publish', True)
        with self.assertRaises(AdmissionFailed) as caught:
            self.start()
        self.assertEqual(self.fence.snapshot()['active_owner'], caught.exception.owner_id)
        self.assertCode('admission_failed_cleanup_required', self.start)
        self.coordinator.cancel(self.client, 1)
        self.assertIsNone(self.fence.snapshot()['active_owner'])
    def test_cancelled_retry_does_not_prepare(self):
        self.start()
        self.coordinator.cancel(self.client, 1)
        count = len(self.factory.events)
        self.assertCode('cancelled_start', self.start)
        self.assertEqual(len(self.factory.events), count)
    def test_stopped_result_cannot_replay_conversion(self):
        owner = self.start()['navigation_id']
        self.assertTrue(self.coordinator.stop_owner(owner))
        self.assertCode('start_no_longer_active', self.start)
    def test_stale_owner_stop_and_cancel_do_not_touch_fresh_owner(self):
        old = self.start()['navigation_id']
        fresh = self.start(2, 'b')['navigation_id']
        self.assertFalse(self.coordinator.stop_owner(old))
        self.assertEqual(self.coordinator.cancel(self.client, 1)['cleanup'], 'not_required')
        self.assertEqual(self.fence.snapshot()['active_owner'], fresh)
    def test_preparation_failure_never_silently_retries(self):
        def fail(candidate, ticket):
            raise ValueError('probe failed')
        self.factory.hook = fail
        with self.assertRaises(ValueError):
            self.start()
        self.assertCode('start_no_longer_active', self.start)
        self.assertIsNone(self.fence.snapshot()['active_owner'])
        self.factory.hook = None
        self.start(2)
    def test_duplicate_pending_is_bounded(self):
        release, thread, result = self.delayed()
        self.assertCode('start_in_progress', self.start)
        self.assertEqual(self.finish(release, thread, result)['label'], 'old')
    def test_preparation_capacity(self):
        self.coordinator = StartCoordinator(self.factory, fence=self.fence, max_preparing=1)
        release, thread, result = self.delayed()
        self.assertCode('preparation_capacity', lambda: self.start(2))
        self.assertEqual(self.finish(release, thread, result).code, 'stale_start')
        self.start(2, 'fresh')
    def test_expiry_and_matching_touch(self):
        owner = self.start()['navigation_id']
        self.now = 50
        self.coordinator.touch_owner(owner)
        self.now = 61
        self.assertFalse(self.coordinator.sweep())
        self.now = 111
        self.assertTrue(self.coordinator.sweep())
        self.assertIsNone(self.fence.snapshot()['active_owner'])
    def test_expired_owner_cancellation(self):
        self.start()
        self.now = 61
        self.assertEqual(self.coordinator.cancel(self.client, 1)['cleanup'], 'confirmed')
    def test_close_during_preparation(self):
        release, thread, result = self.delayed()
        self.coordinator.close()
        self.assertEqual(self.finish(release, thread, result).code, 'fence_closed')
        self.assertNotIn(('publish','old'), self.factory.events)
    def test_close_cleanup_failure_is_retryable(self):
        self.start()
        self.factory.candidates[0].confirm = False
        self.assertCode('cleanup_unconfirmed', self.coordinator.close)
        self.assertIsNotNone(self.fence.snapshot()['active_owner'])
        self.factory.candidates[0].confirm = True
        self.coordinator.close()
        self.assertIsNone(self.fence.snapshot()['active_owner'])
    def test_cancellation_records_before_lifecycle_timeout(self):
        self.start()
        self.coordinator._lock.acquire()
        try:
            self.assertCode('lifecycle_busy', lambda: self.coordinator.cancel(self.client, 1))
            self.assertCode('cancelled_start', lambda: self.fence.request(self.client, 1))
        finally:
            self.coordinator._lock.release()
        self.assertEqual(self.coordinator.cancel(self.client, 1)['cleanup'], 'confirmed')

if __name__ == '__main__':
    unittest.main()
