/**
 * Browser-side OpenTelemetry for Reflex apps, installed by reflex_otel.OtelPlugin.
 *
 * - Every event sent to the backend gets a CLIENT span and a W3C `traceparent`,
 *   so the backend event span joins the browser trace.
 * - Web vitals (LCP, CLS, INP, FCP, TTFB) are reported as spans.
 * - React commits are reported as `react.render` spans via a root <Profiler>
 *   (opt-in; production builds need the react-dom profiling alias the plugin adds).
 * - Socket connects/disconnects are recorded as spans for reconnect tracking.
 *
 * Configuration comes from `env.json` (`OTEL` key), written by the plugin.
 */
import { createElement, Profiler } from "react";
import { context, SpanKind, SpanStatusCode, trace } from "@opentelemetry/api";
import {
  setGlobalErrorHandler,
  W3CTraceContextPropagator,
} from "@opentelemetry/core";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { resourceFromAttributes } from "@opentelemetry/resources";
import {
  BatchSpanProcessor,
  ParentBasedSampler,
  TraceIdRatioBasedSampler,
  WebTracerProvider,
} from "@opentelemetry/sdk-trace-web";
import { onCLS, onFCP, onINP, onLCP, onTTFB } from "web-vitals";
import env from "$/env.json";

const config = env.OTEL ?? {};

const provider = new WebTracerProvider({
  resource: resourceFromAttributes({ "service.name": config.service_name }),
  // Browser spans are trace roots: their sampled flag travels in `traceparent`
  // and a parent-based backend sampler follows it, so sample here.
  sampler: new ParentBasedSampler({
    root: new TraceIdRatioBasedSampler(config.sample_rate ?? 1),
  }),
  spanProcessors: [
    new BatchSpanProcessor(
      new OTLPTraceExporter({ url: config.endpoint, headers: config.headers }),
    ),
  ],
});
const tracer = provider.getTracer("reflex", config.version);

// The exporter swallows its own failures (a collector missing CORS headers
// surfaces only as the browser's console line), so route the first one through
// the same path as any other frontend exception: it reaches the backend's
// frontend_exception_handler and the terminal. Once per page: exports retry on
// every batch and would otherwise repeat the report.
let exportFailureReported = false;
setGlobalErrorHandler((error) => {
  if (exportFailureReported || typeof window.onerror !== "function") {
    return;
  }
  exportFailureReported = true;
  const cause = error?.cause ? ` (${error.cause})` : "";
  const hint = error?.cause
    ? " A collector on another origin must allow CORS requests from this page."
    : "";
  const report = new Error(
    `OtelPlugin: exporting browser spans to ${config.endpoint} failed: ${error?.message ?? error}${cause}.${hint}`,
  );
  report.name = "OtelExportError";
  window.onerror(report.message, null, null, null, report);
});
const propagator = new W3CTraceContextPropagator();

const setter = {
  set(carrier, key, value) {
    carrier[key] = value;
  },
};

// Absolute epoch time (ms) of a performance timeline offset.
const epoch = (offset) => performance.timeOrigin + offset;

let connectCount = 0;

window.__reflex_otel = {
  onEventSend(event) {
    // Fire-and-forget over the socket: a PRODUCER span that marks the send. The
    // browser has no completion signal for an event, so it has no duration.
    const span = tracer.startSpan(event.name, {
      kind: SpanKind.PRODUCER,
      attributes: { "reflex.event.name": event.name },
    });
    propagator.inject(trace.setSpan(context.active(), span), event, setter);
    span.end();
  },
  onSocketConnect() {
    connectCount += 1;
    tracer
      .startSpan("socket.connect", {
        attributes: { "reflex.socket.connect_count": connectCount },
      })
      .end();
  },
  onSocketDisconnect(reason) {
    const span = tracer.startSpan("socket.disconnect", {
      attributes: { "reflex.socket.disconnect_reason": reason },
    });
    // Intentional disconnects (navigation, server shutdown) are not errors.
    if (!reason.startsWith("io ")) {
      span.setStatus({ code: SpanStatusCode.ERROR, message: reason });
    }
    span.end();
    // Unload disconnects happen after the processor's own pagehide flush ran,
    // so the span would otherwise sit in the queue while the page tears down.
    provider.forceFlush();
  },
};

if (config.web_vitals) {
  // FCP/LCP/TTFB values are offsets from the current navigation: activation
  // start for a (pre)rendered page, `navigationStartTime` for a BFCache
  // restore or soft navigation. INP is a duration starting at its interaction;
  // CLS is unitless and reported as an instant.
  const report = (metric) => {
    const activationStart =
      performance.getEntriesByType("navigation")[0]?.activationStart ?? 0;
    const attributes = {
      "web_vital.name": metric.name,
      "web_vital.value": metric.value,
      "web_vital.rating": metric.rating,
      "web_vital.id": metric.id,
      "web_vital.navigation_type": metric.navigationType,
    };
    let startTime = epoch(metric.navigationStartTime || activationStart);
    let endTime = startTime + metric.value;
    if (metric.name === "INP") {
      startTime = epoch(metric.entries[0]?.startTime ?? 0);
      endTime = startTime + metric.value;
    } else if (metric.name === "CLS") {
      startTime = endTime = Date.now();
    }
    tracer
      .startSpan(`web_vital.${metric.name}`, { startTime, attributes })
      .end(endTime);
  };
  onCLS(report);
  onFCP(report);
  onINP(report);
  onLCP(report);
  onTTFB(report);
}

const onRender = (
  id,
  phase,
  actualDuration,
  baseDuration,
  startTime,
  commitTime,
) => {
  tracer
    .startSpan("react.render", {
      startTime: epoch(startTime),
      attributes: {
        "react.profiler.id": id,
        "react.render.phase": phase,
        "react.render.actual_duration_ms": actualDuration,
        "react.render.base_duration_ms": baseDuration,
      },
    })
    .end(epoch(commitTime));
};

/**
 * Root wrapper used by the patched entry: profiles React commits when enabled.
 */
export const OtelRoot = ({ children }) =>
  config.render_timing
    ? createElement(Profiler, { id: "app", onRender }, children)
    : children;
