"""Idle animations with legacy random or configured global-idle timing."""
import math
import random


class Leisure:
    def __init__(self, now, rng=None, delays=None):
        self.rng = rng or random.Random()
        self.delays, self.busy, self.wake_grace = delays, False, False
        self.reset(now)

    def interval(self):
        while True:
            u = max(1e-12, min(1-1e-12, self.rng.random()))
            minutes = 10 + 2.965 * math.sqrt(-2*math.log(u))*math.cos(2*math.pi*self.rng.random())
            if 3 <= minutes <= 30:
                return minutes*60

    def reset(self, now, interval=None, choice=None):
        duration = (self.delays[0] if self.delays is not None else self.interval()) if interval is None else interval
        choice = self.rng.random() if choice is None else choice
        fractions = [2/3] if choice < .4 else [1/3] if choice < .8 else [1/3,2/3] if choice < .9 else []
        self.phase, self.began, self.deadline = 'awake', now, now+duration
        self.snacks = [now+duration*f for f in fractions]
        self.sleep_epoch, self.tail_epoch, self.action_epoch = 0, None, now
        self.wake_grace = False

    def set_busy(self, busy, now):
        previous, self.busy = self.busy, busy
        if busy:
            self.cancel()
            self.deadline, self.snacks, self.wake_grace = None, [], False
        elif previous:
            self.reset(now)

    def wake(self, now):
        if self.busy:
            self.cancel()
            self.deadline = None
            return
        self.reset(now, interval=self.delays[1] if self.delays is not None else None)
        self.wake_grace = True

    def set_delays(self, delays, now):
        self.delays = delays
        if not self.busy and self.phase in {'awake','snacking'}:
            grace = self.wake_grace
            self.reset(now, interval=delays[1] if grace else None)
            self.wake_grace = grace

    def tick(self, now, eligible, snack_duration=None):
        if self.busy or self.deadline is None or self.phase != 'awake':
            return
        due = any(t <= now for t in self.snacks)
        self.snacks = [t for t in self.snacks if t > now]
        if eligible:
            if now >= self.deadline:
                self.enter(now)
            elif due and ((snack_duration is None and self.delays is None) or
                          snack_duration is not None and now+snack_duration < self.deadline):
                self.phase, self.action_epoch = 'snacking', now

    def enter(self, now):
        if self.busy:
            return
        self.phase, self.action_epoch, self.tail_epoch, self.snacks = 'entering', now, None, []

    def cancel(self):
        self.phase, self.tail_epoch = 'awake', None

    def click(self, now, wake=None):
        if self.phase not in ('entering','sleeping'):
            return False
        if wake is None:
            wake = self.rng.random() < .5
        if wake:
            self.phase, self.action_epoch, self.tail_epoch = 'waking', now, None
        elif self.phase == 'sleeping' and (self.tail_epoch is None or now-self.tail_epoch >= 1.44):
            self.tail_epoch = now
        return True

    def position(self, clips, now):
        elapsed = now-self.action_epoch
        if self.phase == 'snacking':
            if elapsed >= clips['snack'].total_duration/1000:
                self.phase = 'awake'
            else:
                return 'snack', clips['snack'].frame(elapsed, True)
        if self.phase == 'entering':
            duration = clips['sleep_entry'].total_duration/1000
            if elapsed >= duration:
                self.phase, self.sleep_epoch = 'sleeping', self.action_epoch+duration
            else:
                return 'sleep_entry', clips['sleep_entry'].frame(elapsed, True)
        if self.phase == 'sleeping':
            return 'sleep_body', clips['sleep_body'].frame(now-self.sleep_epoch)
        if self.phase == 'waking':
            if elapsed >= 2*clips['left'].total_duration/1000:
                self.wake(now)
            else:
                return 'left', clips['left'].frame(elapsed)
        return None
