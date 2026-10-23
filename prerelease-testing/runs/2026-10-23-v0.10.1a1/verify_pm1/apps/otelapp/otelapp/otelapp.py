"""verify_pm1 otel/apscheduler app: real-world import-time threads under the 0.10.1a1 prod fork preload.

At import: OpenTelemetry SDK TracerProvider + BatchSpanProcessor (worker thread) with a FILE exporter
(one line per span with the exporting pid), MeterProvider + PeriodicExportingMetricReader (thread) with
a file exporter, ReflexInstrumentor().instrument(...) (reflex-otel 0.2.0), an APScheduler
BackgroundScheduler (thread) with a 0.5 s interval job, and a logging QueueListener.
/api/otelstat reports per-worker thread liveness and counters; the files show which pids exported.
"""

import logging
import logging.handlers
import os
import queue
import threading
import time

import reflex as rx
from apscheduler.schedulers.background import BackgroundScheduler
from opentelemetry import trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    MetricExporter,
    MetricExportResult,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from reflex_otel import ReflexInstrumentor
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

if os.environ.get("EXPECT_VENV"):  # venv guard
    assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__

IMPORT_PID = os.getpid()
OUT = os.environ.get("OTELAPP_OUT", os.path.abspath("otelapp-out"))
os.makedirs(OUT, exist_ok=True)
SPANS = {"exported": 0, "pid": None}
METRICS = {"exported": 0, "pid": None}
JOB = {"n": 0, "pid": None}


class FileSpanExporter(SpanExporter):
    def export(self, spans):
        with open(os.path.join(OUT, "spans.log"), "a") as f:
            for s in spans:
                f.write(f"pid={os.getpid()} name={s.name}\n")
        SPANS["exported"] += len(spans)
        SPANS["pid"] = os.getpid()
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


class FileMetricExporter(MetricExporter):
    def export(self, metrics_data, timeout_millis=10_000, **kw):
        with open(os.path.join(OUT, "metrics.log"), "a") as f:
            f.write(f"pid={os.getpid()} export\n")
        METRICS["exported"] += 1
        METRICS["pid"] = os.getpid()
        return MetricExportResult.SUCCESS

    def force_flush(self, timeout_millis=10_000):
        return True

    def shutdown(self, timeout_millis=30_000, **kw):
        pass


provider = TracerProvider()
BSP = BatchSpanProcessor(FileSpanExporter(), schedule_delay_millis=300)
provider.add_span_processor(BSP)
READER = PeriodicExportingMetricReader(FileMetricExporter(), export_interval_millis=1000)
meter_provider = MeterProvider(metric_readers=[READER])
ReflexInstrumentor().instrument(tracer_provider=provider, meter_provider=meter_provider)
tracer = trace.get_tracer("otelapp")


def _job():
    JOB["n"] += 1
    JOB["pid"] = os.getpid()


SCHED = BackgroundScheduler()
SCHED.add_job(_job, "interval", seconds=0.5)
SCHED.start()

_q: queue.Queue = queue.Queue()
qlog = logging.getLogger("otelapp.queued")
qlog.setLevel(logging.INFO)
qlog.propagate = False
qlog.addHandler(logging.handlers.QueueHandler(_q))
_qfh = logging.FileHandler(os.path.join(OUT, "queued.log"))
_qfh.setFormatter(logging.Formatter("pid=%(process)d %(message)s"))
LISTENER = logging.handlers.QueueListener(_q, _qfh)
LISTENER.start()
dlog = logging.getLogger("otelapp.direct")
dlog.setLevel(logging.INFO)
dlog.propagate = False
_dfh = logging.FileHandler(os.path.join(OUT, "direct.log"))
_dfh.setFormatter(logging.Formatter("pid=%(process)d %(message)s"))
dlog.addHandler(_dfh)
qlog.info("import")
dlog.info("import")


def _threads():
    return sorted(t.name for t in threading.enumerate())


async def otelstat(request):
    with tracer.start_as_current_span("manual-span"):
        pass
    qlog.info("otelstat")
    dlog.info("otelstat")
    return JSONResponse(
        {
            "pid": os.getpid(),
            "imported_in_this_process": IMPORT_PID == os.getpid(),
            "threads": _threads(),
            "spans_exported_here": SPANS["exported"] if SPANS["pid"] == os.getpid() else 0,
            "metrics_exported_here": METRICS["exported"] if METRICS["pid"] == os.getpid() else 0,
            "sched_running": SCHED.running,
            "sched_thread_alive": bool(SCHED._thread and SCHED._thread.is_alive()),
            "job_runs": JOB["n"],
            "job_pid": JOB["pid"],
            "qlistener_alive": bool(LISTENER._thread and LISTENER._thread.is_alive()),
            "queue_depth": _q.qsize(),
        }
    )


api = Starlette(routes=[Route("/api/otelstat", otelstat)])


class State(rx.State):
    count: int = 0

    @rx.event
    def inc(self):
        self.count += 1


def index() -> rx.Component:
    return rx.vstack(rx.heading("otelapp"), rx.text(State.count), rx.button("inc", on_click=State.inc))


app = rx.App(api_transformer=api)
app.add_page(index)
