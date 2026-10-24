from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from tools.start_fence import AdmissionFailed, FenceError, StartFence

class Clock:
    def __init__(self): self.now=0.0
    def __call__(self): return self.now
    def advance(self,seconds): self.now+=seconds

class FenceTests(unittest.TestCase):
    def setUp(self): self.clock=Clock();self.gate=StartFence(clock=self.clock);self.started=[]
    def assertCode(self,code,operation):
        with self.assertRaises(FenceError) as caught: operation()
        self.assertEqual(caught.exception.code,code)
    def client(self): return self.gate.open_client()
    def admit(self,ticket): return self.gate.admit(ticket,self.started.append)
    def test_admission_is_idempotent(self):
        c=self.client();t=self.gate.request(c,1);owner=self.admit(t)
        self.assertEqual(self.gate.request(c,1),t);self.assertEqual(self.admit(t),owner)
        self.assertEqual(self.started,[owner])
    def test_cancel_before_start_arrives(self):
        c=self.client();self.assertIsNone(self.gate.cancel(c,1))
        self.assertCode('cancelled_start',lambda:self.gate.request(c,1));self.assertEqual(self.started,[])
        self.admit(self.gate.request(c,2));self.assertEqual(len(self.started),1)
    def test_cancel_during_preparation_blocks_admission(self):
        c=self.client();t=self.gate.request(c,1);self.gate.cancel(c,1)
        self.assertCode('cancelled_start',lambda:self.admit(t));self.assertEqual(self.started,[])
    def test_new_revision_invalidates_old_preparation(self):
        c=self.client();old=self.gate.request(c,1);new=self.gate.request(c,2)
        self.assertCode('stale_start',lambda:self.admit(old));self.admit(new);self.assertEqual(len(self.started),1)
    def test_delayed_lower_revision_cannot_replace_new(self):
        c=self.client();new=self.gate.request(c,2);owner=self.admit(new)
        self.assertCode('stale_start',lambda:self.gate.request(c,1))
        self.assertEqual(self.gate.snapshot()['active_owner'],owner)
    def test_newer_registered_client_fences_late_old_client(self):
        old=self.client();new=self.client();owner=self.admit(self.gate.request(new,1))
        self.assertCode('client_superseded',lambda:self.gate.request(old,99))
        self.assertEqual(self.gate.snapshot()['active_owner'],owner)
    def test_opening_client_alone_does_not_takeover(self):
        a=self.client();first=self.gate.request(a,1);owner=self.admit(first);self.client()
        self.assertEqual(self.gate.request(a,1),first)
        self.assertEqual(self.gate.snapshot()['active_owner'],owner)
    def test_explicit_new_handle_can_reclaim_after_takeover(self):
        a=self.client();b=self.client();owner=self.admit(self.gate.request(b,1))
        self.assertCode('client_superseded',lambda:self.gate.request(a,1))
        fresh=self.client();ticket=self.gate.request(fresh,1)
        self.assertCode('owner_busy',lambda:self.admit(ticket))
        self.assertTrue(self.gate.finish(owner));self.admit(ticket)
    def test_old_cancel_does_not_cancel_new_revision(self):
        c=self.client();t=self.gate.request(c,1);old_owner=self.admit(t)
        new=self.gate.request(c,2);self.assertEqual(self.gate.cancel(c,1),old_owner)
        self.gate.finish(old_owner);new_owner=self.admit(new)
        self.assertIsNone(self.gate.cancel(c,1));self.assertEqual(self.gate.snapshot()['active_owner'],new_owner)
    def test_cancel_returns_active_owner_until_confirmed_cleanup(self):
        c=self.client();owner=self.admit(self.gate.request(c,1));self.assertEqual(self.gate.cancel(c,1),owner)
        next_ticket=self.gate.request(c,2);self.assertCode('owner_busy',lambda:self.admit(next_ticket))
        self.assertTrue(self.gate.finish(owner));self.admit(next_ticket)
    def test_stale_cleanup_cannot_release_new_owner(self):
        c=self.client();old=self.admit(self.gate.request(c,1));self.gate.cancel(c,1);self.gate.finish(old)
        owner=self.admit(self.gate.request(c,2));self.assertFalse(self.gate.finish(old))
        self.assertEqual(self.gate.snapshot()['active_owner'],owner)
    def test_other_client_cancel_is_owner_scoped(self):
        a=self.client();b=self.client();owner=self.admit(self.gate.request(b,1))
        self.assertIsNone(self.gate.cancel(a,100));self.assertEqual(self.gate.snapshot()['active_owner'],owner)
    def test_callback_failure_reserves_slot_and_never_retries_action(self):
        c=self.client();ticket=self.gate.request(c,1);calls=[]
        def fail(owner): calls.append(owner);raise RuntimeError('partial admission')
        with self.assertRaises(AdmissionFailed) as failure: self.gate.admit(ticket,fail)
        owner=failure.exception.owner_id
        with self.assertRaises(AdmissionFailed): self.gate.admit(ticket,fail)
        self.assertEqual(calls,[owner]);self.assertEqual(self.gate.snapshot()['active_owner'],owner)
        self.gate.cancel(c,1);self.gate.finish(owner);self.admit(self.gate.request(c,2))
    def test_idle_handles_expire_without_resurrection(self):
        c=self.client();ticket=self.gate.request(c,1);self.clock.advance(61)
        self.assertCode('unknown_client',lambda:self.admit(ticket))
        self.assertCode('unknown_client',lambda:self.gate.request(c,2))
        self.assertEqual(self.gate.snapshot()['clients'],0)
    def test_expired_active_owner_remains_owned_until_cleanup(self):
        c=self.client();owner=self.admit(self.gate.request(c,1));self.clock.advance(61)
        self.assertEqual(self.gate.expired_owner(),owner)
        self.assertCode('client_expired',lambda:self.gate.touch(c))
        self.assertEqual(self.gate.cancel(c,1),owner);self.gate.finish(owner)
        self.assertEqual(self.gate.snapshot()['clients'],0)
    def test_heartbeat_renews_handle(self):
        c=self.client();self.clock.advance(50);self.gate.touch(c);self.clock.advance(20)
        self.gate.request(c,1)
    def test_bounded_registry_reclaims_only_safe_idle_records(self):
        gate=StartFence(max_clients=2,clock=self.clock);a=gate.open_client();gate.open_client()
        self.assertCode('client_capacity',lambda:gate.open_client());self.clock.advance(61)
        self.assertIsInstance(gate.open_client(),str);self.assertEqual(gate.snapshot()['clients'],1)
        self.assertCode('unknown_client',lambda:gate.request(a,1))
    def test_active_record_is_not_silently_evicted(self):
        gate=StartFence(max_clients=1,clock=self.clock);c=gate.open_client();owner=gate.admit(gate.request(c,1),lambda owner:None)
        self.clock.advance(61);self.assertCode('client_capacity',lambda:gate.open_client())
        self.assertEqual(gate.expired_owner(),owner);gate.finish(owner);gate.open_client()
    def test_closed_epoch_and_foreign_ticket_rejected(self):
        c=self.client();t=self.gate.request(c,1);other=StartFence(clock=self.clock)
        self.assertCode('stale_epoch',lambda:other.check(t))
        self.assertIsNone(self.gate.close());self.assertCode('fence_closed',lambda:self.gate.request(c,2))
        self.assertCode('fence_closed',lambda:self.gate.open_client())
    def test_close_returns_active_cleanup_identity(self):
        c=self.client();owner=self.admit(self.gate.request(c,1))
        self.assertEqual(self.gate.close(),owner);self.assertTrue(self.gate.finish(owner));self.assertIsNone(self.gate.close())
    def test_invalid_revisions_and_clients(self):
        c=self.client()
        for revision in (0,-1,True,1.5,2**53): self.assertCode('invalid_revision',lambda r=revision:self.gate.request(c,r))
        self.assertCode('unknown_client',lambda:self.gate.request('unknown',1))
        self.assertCode('unknown_client',lambda:self.gate.cancel('unknown',1))
    def test_concurrent_revisions_only_latest_can_admit(self):
        c=self.client();barrier=threading.Barrier(2)
        def request(revision):
            barrier.wait()
            try: return self.gate.request(c,revision)
            except FenceError: return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(request,1),pool.submit(request,2)]
            tickets=[future.result(timeout=2) for future in futures]
        newest=next(t for t in tickets if t and t.revision==2)
        for ticket in tickets:
            if ticket and ticket.revision==1: self.assertCode('stale_start',lambda:self.admit(ticket))
        self.admit(newest);self.assertEqual(len(self.started),1)
    def test_concurrent_duplicate_admission_runs_action_once(self):
        c=self.client();ticket=self.gate.request(c,1);barrier=threading.Barrier(2)
        def admit(): barrier.wait();return self.admit(ticket)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a,b=pool.submit(admit),pool.submit(admit);owners=[a.result(timeout=2),b.result(timeout=2)]
        self.assertEqual(owners[0],owners[1]);self.assertEqual(self.started,[owners[0]])

if __name__=='__main__': unittest.main()
