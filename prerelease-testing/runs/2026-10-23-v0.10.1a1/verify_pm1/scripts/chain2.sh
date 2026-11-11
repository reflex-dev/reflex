#!/usr/bin/env bash
# chain2.sh: sequential follow-up runs (one server set at a time).
set -u; : "${SB:?}"; V=$SB/apps/verify_pm1; cd "$V" || exit 2
export REFLEX_REDIS_URL=redis://localhost:8739 REFLEX_TELEMETRY_ENABLED=false
echo "#### A1 new fork, 40x /api/log (QueueListener drop count) $(date +%T)"; ./scripts/logrun.sh new new-be-log-fork 8721
echo "#### A2 new spawn workaround $(date +%T)"; ./scripts/logrun.sh new new-be-log-spawn 8721 REFLEX_BACKEND_START_METHOD=spawn
echo "#### A3 new fork + PYTHONWARNINGS=default (does CPython's fork+threads DeprecationWarning surface?) $(date +%T)"; ./scripts/logrun.sh new new-be-log-pywarn 8721 PYTHONWARNINGS=default
echo "#### A4 prev fork, 40x /api/log (baseline) $(date +%T)"; ./scripts/logrun.sh prev prev-be-log-fork 8721
echo "#### B1 otel+apscheduler app, new fork $(date +%T)"; ./scripts/otelrun.sh verify_pm1-otel otel-fork 8722
echo "#### B2 otel+apscheduler app, new spawn $(date +%T)"; ./scripts/otelrun.sh verify_pm1-otel otel-spawn 8722 REFLEX_BACKEND_START_METHOD=spawn
echo "#### C1 py3.14 backend-only new $(date +%T)"; ./scripts/probe_run.sh process_model-py314-new py314-new-be 8723
echo "#### C2 py3.14 backend-only prev $(date +%T)"; ./scripts/probe_run.sh process_model-py314-prev py314-prev-be 8723
echo "#### C3 py3.14 FULL-STACK prev (claim: any prod run on 3.14 regresses) $(date +%T)"; ./scripts/probe_run.sh process_model-py314-prev py314-prev-full prod 8720
echo "#### C4 py3.14 FULL-STACK new $(date +%T)"; ./scripts/probe_run.sh process_model-py314-new py314-new-full prod 8720
echo "#### done $(date +%T)"; ss -ltnp 2>/dev/null | grep -E ':(87[23][0-9]|37[23][0-9])\b' | grep -v 8739 || echo "no listeners left on 8720-8738"
