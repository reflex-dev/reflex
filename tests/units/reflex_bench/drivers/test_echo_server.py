"""Tests for reflex_bench.drivers.echo_server.

The echo server's answers are exercised by the generator's tests; these check
the process that the calibration runs it in.
"""

from __future__ import annotations

from reflex_bench.drivers import events
from reflex_bench.drivers.echo_server import EchoProcess
from reflex_bench.drivers.events import EventShape, LoadPlan, run_load

STATE = "reflex___state____state.playground___state____bench_state"
SEQ_VAR = "last_seq_rx_state_"


def test_echo_process_answers_a_load_and_stops():
    echo = EchoProcess(delta_key=STATE, seq_var=SEQ_VAR)
    url = echo.start()
    try:
        shape = EventShape(
            name=f"{STATE}.set_seq",
            payload=events.seq_payload,
            delta_key=STATE,
            seq_var=SEQ_VAR,
        )
        result = run_load(
            LoadPlan(
                backend_url=url,
                reflex_version=None,
                shape=shape,
                sessions=2,
                mode="closed",
                rate=None,
                warmup_s=0.1,
                duration_s=0.3,
            )
        )
    finally:
        echo.stop()
    assert result.answered > 0
    assert result.unanswered == 0
    assert result.session_errors == []
    assert echo._proc is not None
    assert not echo._proc.is_alive()
    echo.stop()


def test_echo_process_exits_when_its_parent_goes_away():
    echo = EchoProcess(delta_key=STATE, seq_var=SEQ_VAR)
    echo.start()
    proc, conn = echo._proc, echo._conn
    assert proc is not None
    assert conn is not None
    try:
        # Closing the parent's end of the pipe is what any exit of the parent does.
        conn.close()
        proc.join(10)
        assert proc.exitcode is not None
    finally:
        echo.stop()
