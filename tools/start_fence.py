"""R2A: bounded in-memory Start ownership fencing. No HTTP, media or workers.

The caller authenticates requests, prepares sources outside this lock, and
serializes worker replacement. Only a short nonblocking admission action runs
inside admit(). Real backend/adapter wiring is deliberately a later checkpoint.
"""
from dataclasses import dataclass
import math
import secrets
import threading
import time

MAX_REVISION=2**53-1

class FenceError(ValueError):
    def __init__(self,code): self.code=code;super().__init__(code)

class AdmissionFailed(RuntimeError):
    def __init__(self,owner_id):
        self.owner_id=owner_id
        super().__init__('admission_failed_cleanup_required')

@dataclass(frozen=True)
class StartTicket:
    epoch: str
    client: str
    revision: int
    sequence: int

@dataclass
class _Client:
    deadline: float
    client_epoch: int
    revision: int=0
    cancelled_through: int=0
    ticket: object=None
    owner_id: object=None
    outcome: str='none'

class StartFence:
    def __init__(self,max_clients=32,lease_seconds=60,clock=time.monotonic):
        if type(max_clients) is not int or not 1<=max_clients<=1024: raise ValueError('Invalid client limit')
        if type(lease_seconds) not in (int,float) or not math.isfinite(lease_seconds) or lease_seconds<=0: raise ValueError('Invalid control lease')
        self._limit=max_clients;self._lease=lease_seconds;self._clock=clock
        self._epoch=secrets.token_hex(16);self._lock=threading.Lock();self._clients={}
        self._sequence=0;self._client_sequence=0;self._owner_epoch=0
        self._latest=None;self._active=None;self._closed=False
    def _prune(self):
        now=self._clock()
        active_client=self._active[0].client if self._active else None
        for key,record in list(self._clients.items()):
            if record.deadline<=now and key!=active_client:
                if self._latest and self._latest.client==key: self._latest=None
                del self._clients[key]
    def _record(self,client,allow_expired=False):
        if self._closed: raise FenceError('fence_closed')
        self._prune()
        record=self._clients.get(client) if isinstance(client,str) else None
        if record is None: raise FenceError('unknown_client')
        if record.deadline<=self._clock() and not allow_expired: raise FenceError('client_expired')
        return record
    @staticmethod
    def _revision(value,allow_zero=False):
        if type(value) is not int or not (0 if allow_zero else 1)<=value<=MAX_REVISION:
            raise FenceError('invalid_revision')
    def open_client(self):
        with self._lock:
            if self._closed: raise FenceError('fence_closed')
            self._prune()
            if len(self._clients)>=self._limit: raise FenceError('client_capacity')
            client=secrets.token_hex(24)
            while client in self._clients: client=secrets.token_hex(24)
            self._client_sequence+=1
            self._clients[client]=_Client(self._clock()+self._lease,self._client_sequence)
            return client
    def touch(self,client):
        with self._lock:
            record=self._record(client);record.deadline=self._clock()+self._lease
    def request(self,client,revision):
        self._revision(revision)
        with self._lock:
            record=self._record(client)
            if record.client_epoch<self._owner_epoch: raise FenceError('client_superseded')
            if revision<=record.cancelled_through: raise FenceError('cancelled_start')
            if revision<record.revision: raise FenceError('stale_start')
            if revision==record.revision:
                self._check(record.ticket)
                return record.ticket
            self._sequence+=1
            ticket=StartTicket(self._epoch,client,revision,self._sequence)
            record.revision=revision;record.ticket=ticket;record.owner_id=None;record.outcome='none'
            record.deadline=self._clock()+self._lease;self._latest=ticket
            self._owner_epoch=record.client_epoch
            return ticket
    def _check(self,ticket):
        if not isinstance(ticket,StartTicket) or ticket.epoch!=self._epoch: raise FenceError('stale_epoch')
        record=self._record(ticket.client)
        if record.client_epoch<self._owner_epoch: raise FenceError('client_superseded')
        if ticket.revision<=record.cancelled_through: raise FenceError('cancelled_start')
        if record.ticket!=ticket or self._latest!=ticket: raise FenceError('stale_start')
        return record
    def check(self,ticket):
        with self._lock: self._check(ticket)
    def admit(self,ticket,action):
        """action(owner_id) must be short, nonblocking and never re-enter the fence.

        Metadata/probing and old-worker stop/reap happen before this method.
        A failed action reserves ownership until caller cleanup calls finish().
        """
        if not callable(action): raise TypeError('Admission action must be callable')
        with self._lock:
            record=self._check(ticket)
            if record.owner_id is not None:
                if record.outcome=='failed': raise AdmissionFailed(record.owner_id)
                return record.owner_id
            if self._active is not None: raise FenceError('owner_busy')
            owner_id=secrets.token_hex(24)
            record.owner_id=owner_id;record.outcome='admitting';self._active=(ticket,owner_id)
            try: action(owner_id)
            except BaseException as error:
                record.outcome='failed'
                raise AdmissionFailed(owner_id) from error
            record.outcome='admitted'
            return owner_id
    def cancel(self,client,through_revision):
        """Record cancellation even before the matching Start reaches request().

        Return the matching active owner to stop, or None. Caller must recheck
        its worker's owner before stop/reap, then call finish(owner_id).
        """
        self._revision(through_revision,allow_zero=True)
        with self._lock:
            record=self._record(client,allow_expired=True)
            record.cancelled_through=max(record.cancelled_through,through_revision)
            if self._latest and self._latest.client==client and self._latest.revision<=record.cancelled_through:
                self._latest=None
            if self._active:
                ticket,owner_id=self._active
                if ticket.client==client and ticket.revision<=record.cancelled_through: return owner_id
            return None
    def finish(self,owner_id):
        """Release only after confirmed worker cleanup; stale finish is harmless."""
        with self._lock:
            if self._active is None or self._active[1]!=owner_id: return False
            self._active=None;self._prune();return True
    def expired_owner(self):
        """Manager sweeps this and cleans the returned owner; no automatic kill."""
        with self._lock:
            self._prune()
            if self._active:
                ticket,owner_id=self._active
                if self._clients[ticket.client].deadline<=self._clock(): return owner_id
            return None
    def snapshot(self):
        with self._lock:
            self._prune()
            return dict(clients=len(self._clients),max_clients=self._limit,closed=self._closed,
                latest_sequence=self._latest.sequence if self._latest else None,
                active_owner=self._active[1] if self._active else None)
    def close(self):
        """Invalidate clients/tickets and return any owner still needing cleanup."""
        with self._lock:
            self._closed=True;self._latest=None
            return self._active[1] if self._active else None
