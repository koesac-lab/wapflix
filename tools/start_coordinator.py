"""R2B.2 coordinator only: no HTTP routes, media factory or runtime fixture.

Factory contract (required injection): prepare(immutable_spec, ticket) returns a
candidate without launching a converter. Preparation must enforce its own existing
probe deadline and return no live resources. candidate.publish(owner_id) is short,
synchronous, nonblocking, and must not re-enter this coordinator/fence. It binds a
navigation and schedules admitted work; snapshot() returns current metadata, not a
stored frame/caption payload. stop() returns literal True ONLY after stop/reap.
All blocking factory operations must have bounded deadlines supplied by the real
factory in R2B.3. Python cannot forcibly terminate an arbitrary injected callback.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import math
import threading
from .start_fence import StartFence, FenceError

class CoordinatorError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

@dataclass
class _Owner:
    ticket: object
    owner_id: str
    candidate: object
    admitted: bool = False

class StartCoordinator:
    def __init__(self, factory, *, fence=None, max_preparing=4, lock_timeout=5):
        if factory is None or not callable(getattr(factory, 'prepare', None)):
            raise ValueError('A real factory is required; no runtime fallback')
        if type(max_preparing) is not int or not 1 <= max_preparing <= 32:
            raise ValueError('Invalid preparation bound')
        if type(lock_timeout) not in (int, float) or not math.isfinite(lock_timeout) or not 0 < lock_timeout <= 5:
            raise ValueError('Invalid lifecycle wait budget')
        self.fence = fence if fence is not None else StartFence()
        self.factory = factory
        self._lock = threading.Lock()
        self._timeout = lock_timeout
        self._slots = threading.BoundedSemaphore(max_preparing)
        self._preparing = set()
        self._pending_lock = threading.Lock()
        self._owner = None
        self._last = None  # only globally latest outcome; older tickets fail core checks
        self._closed = False

    @contextmanager
    def _lifecycle(self):
        if not self._lock.acquire(timeout=self._timeout):
            raise CoordinatorError('lifecycle_busy')
        try:
            yield
        finally:
            self._lock.release()

    def _replay(self, ticket):
        self.fence.check(ticket)
        if self._owner and self._owner.ticket == ticket:
            if not self._owner.admitted:
                raise CoordinatorError('admission_failed_cleanup_required')
            return self._owner.candidate.snapshot()
        with self._pending_lock:
            if ticket in self._preparing:
                raise CoordinatorError('start_in_progress')
        if self._last == ticket:
            raise CoordinatorError('start_no_longer_active')
        return None

    def start(self, client, revision, immutable_spec):
        # Record intent before taking the lifecycle lock or doing slow work.
        ticket = self.fence.request(client, revision)
        with self._lifecycle():
            replay = self._replay(ticket)
            if replay is not None:
                return replay
            if self._closed:
                raise CoordinatorError('coordinator_closed')
            if not self._slots.acquire(blocking=False):
                raise CoordinatorError('preparation_capacity')
            with self._pending_lock:
                self._preparing.add(ticket)
            self._last = ticket
        try:
            # Must use an immutable caller-owned configuration snapshot, never app.start.
            candidate = self.factory.prepare(immutable_spec, ticket)
            with self._lifecycle():
                self.fence.check(ticket)
                if self._owner:
                    self._stop_locked(self._owner.owner_id)
                # Cancellation/supersession during stop/reap is checked in admit.
                def publish(owner_id):
                    self._owner = _Owner(ticket, owner_id, candidate)
                    candidate.publish(owner_id)
                    self._owner.admitted = True
                self.fence.admit(ticket, publish)
                return candidate.snapshot()
        finally:
            # Separate bookkeeping lock never surrounds callbacks or slow work.
            with self._pending_lock:
                self._preparing.discard(ticket)
            self._slots.release()

    def _stop_locked(self, owner_id):
        if self._owner is None or self._owner.owner_id != owner_id:
            return False
        try:
            confirmed = self._owner.candidate.stop()
        except Exception as error:
            raise CoordinatorError('cleanup_unconfirmed') from error
        if confirmed is not True:
            raise CoordinatorError('cleanup_unconfirmed')
        if not self.fence.finish(owner_id):
            raise CoordinatorError('ownership_mismatch')
        self._owner = None
        return True

    def cancel(self, client, through_revision):
        # Out of band: tombstone is recorded before waiting for lifecycle cleanup.
        owner = self.fence.cancel(client, through_revision)
        if owner is None:
            return {'fence_recorded': True, 'cleanup': 'not_required'}
        with self._lifecycle():
            self._stop_locked(owner)  # exact-owner recheck protects replacements
        return {'fence_recorded': True, 'cleanup': 'confirmed'}

    def stop_owner(self, owner_id):
        """Navigation layer passes a validated owner, never an arbitrary session ID."""
        with self._lifecycle():
            return self._stop_locked(owner_id)

    def sweep(self):
        owner = self.fence.expired_owner()
        if owner is None:
            return False
        with self._lifecycle():
            # Recheck expiry after the wait: matching traffic may have renewed it.
            if self.fence.expired_owner() != owner:
                return False
            return self._stop_locked(owner)

    def touch_owner(self, owner_id):
        with self._lifecycle():
            if self._owner is None or self._owner.owner_id != owner_id or not self._owner.admitted:
                raise CoordinatorError('owner_not_active')
            self.fence.touch(self._owner.ticket.client)

    def close(self):
        # Fence first: blocked preparation can never publish after shutdown.
        owner = self.fence.close()
        with self._lifecycle():
            self._closed = True
            if owner is not None:
                self._stop_locked(owner)
