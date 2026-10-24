from dataclasses import dataclass

from .vision import Observation


@dataclass
class Action:
    kind: str
    point: tuple[float, float]


class Controller:
    def __init__(self, latency=.035, max_casts=10):
        self.latency = latency
        self.max_casts = max_casts
        self.casts = 0
        self.phase = "ready"
        self.last_action = -100.0
        self.previous = None
        self.velocity = 0.0
        self.armed = True
        self.last_target = None
        self.finished = False
        self.decision = 'waiting for skill'
        self.skill_clicks = 0
        self.ready_since = None

    def step(self, obs: Observation, now: float, frame_age: float = 0.):
        if self.finished:
            return None
        action = None
        gap = now - self.last_action
        if obs.state == 'ready':
            if self.ready_since is None:
                self.ready_since = now
            # Resynchronize after a missed/manual reward dismissal. Do not
            # repeat a cast just because its green-button animation lingers.
            if self.phase == 'playing' and now-self.ready_since >= .35 and gap > 1.2:
                self.phase = 'ready'
        else:
            self.ready_since = None
        if obs.state != "skill":
            self.previous = None
            self.velocity = 0.0
        if obs.state == "reward" and gap > 1.2:
            action = Action("dismiss", obs.dismiss_point or (.5, .89))
            self.phase = "collecting"
            self.armed = True
            self.last_target = None
            self.decision = 'waiting for green cast button'
        elif obs.state == "ready" and self.phase in ("ready", "collecting") and gap > 1.2:
            if self.casts >= self.max_casts:
                self.finished = True
            else:
                action = Action("cast", (.5, .89))
                self.casts += 1
                self.phase = "waiting"
                self.decision = 'waiting for bite'
        elif obs.state == "bite" and self.phase in ("ready", "waiting") and gap > .15:
            action = Action("hook", (.5, .89))
            self.phase = "playing"
            self.armed = True
        elif obs.state == "skill" and self.phase != 'collecting':
            self.phase = "playing"
            x = obs.marker
            a, b = obs.target
            if self.previous:
                old_x, old_t = self.previous
                dt = now-old_t
                if 0 < dt < .2 and abs(x-old_x) < 100:
                    speed = (x-old_x)/dt
                    self.velocity = .5*self.velocity + .5*speed
                else:
                    self.velocity = 0.0
            self.previous = (x, now)
            changed = self.last_target is not None and max(abs(a-self.last_target[0]), abs(b-self.last_target[1])) > 8
            if gap > .45 and (x < a-5 or x > b+5 or changed):
                self.armed = True
            margin = min(10, (b-a)*.2)
            predicted = x + self.velocity*(self.latency+max(0., frame_age))
            self.decision = ('waiting for next check' if not self.armed else
                             'click cooldown' if gap <= .25 else 'waiting for target')
            if self.armed and gap > .25 and a+margin <= predicted <= b-margin:
                action = Action("skill", (.5, .89))
                self.armed = False
                self.last_target = (a, b)
                self.skill_clicks += 1
                self.decision = 'CLICK sent'
        if action:
            self.last_action = now
        return action
