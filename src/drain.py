"""A wall-clock budget for a capped drain.

The EP drains (written questions, committee documents) cap their detail
fetches by COUNT: 300 a run at 0.65s apart, "3.3 minutes". On 19 September
2026 the EU weekly was cancelled twice at the written-question step: 300
fetches against an API answering slowly or with 429s, each retry backing off
2s, 8s, 20s, is not 3.3 minutes but the rest of the job. A count cap bounds
the API budget; only a clock bounds the job. Both runs died silently at the
same step and the steps after it -- triage, edition, tracker, 5CA -- never
ran.
"""

import time

DEFAULT_S = 600.0     # ten minutes: a drain is one step of a job, not the job


class Budget:
    def __init__(self, seconds=DEFAULT_S, clock=None):
        self.seconds = float(seconds)
        self._clock = clock or time.monotonic
        self._start = self._clock()

    def spent(self):
        return self._clock() - self._start

    def exhausted(self):
        return self.spent() >= self.seconds

    def disclose(self, what, done):
        """The line a drain prints when the clock, not the count, stops it."""
        return ("  time budget ({0:.0f}s) reached after {1} {2}; the rest drains "
                "on later runs -- disclosed, not silent".format(self.seconds, done, what))
