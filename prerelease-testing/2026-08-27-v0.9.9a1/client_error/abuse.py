"""Raw socket.io abuse tester for the client_error event (#6827).

Connects to the reflex backend as a real client (linking a token so its sid is
"known"), then emits a battery of hostile client_error payloads:
  - non-dict payloads (str, list, int, None)
  - control chars / ANSI escapes / rich markup / newlines (log-forging attempt)
  - oversized message (10MB string) -> tests bounding + socket buffer limit
  - flood (> per-sid and > per-window limits) -> tests rate limiting

Usage: python abuse.py <backend_url> <namespace_path>
Prints what the server accepts/rejects; watch the backend log for the effect.
"""

import asyncio
import sys

import socketio


async def run(backend_url: str, ns: str):
    token = "abuse-token-12345"
    results = []

    def new_client():
        return socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)

    # --- Connect with a linked token so our sid is "known" ------------------
    sio = new_client()

    @sio.on("*", namespace=ns)
    def catchall(event, data):
        results.append(f"RECV event={event!r} data={str(data)[:120]!r}")

    await sio.connect(
        f"{backend_url}?token={token}",
        socketio_path="_event",
        namespaces=[ns],
        transports=["websocket"],
        wait_timeout=10,
    )
    print(f"CONNECTED sid={sio.get_sid(ns)} ns={ns}")
    await asyncio.sleep(0.5)

    async def emit(label, payload, namespace=ns):
        try:
            await sio.emit("client_error", payload, namespace=namespace)
            await asyncio.sleep(0.2)
            print(f"SENT   {label}: accepted-by-transport")
        except Exception as e:  # noqa: BLE001
            print(f"SENT   {label}: EXC {type(e).__name__}: {e}")

    # 1. Non-dict payloads (should be ignored server-side, no crash)
    await emit("non_dict_str", "i am a string")
    await emit("non_dict_list", ["a", "b"])
    await emit("non_dict_int", 12345)
    await emit("non_dict_none", None)

    # 2. Control chars / ANSI / markup / newlines (log-forging attempt)
    forge = (
        "\x1b[31mFAKE-RED\x1b[0m line1\nline2\r\n"
        "[bold red]RICH-MARKUP[/bold red] \x00\x07\x08 "
        "2099-01-01 00:00:00 | ERROR | forged-log-line"
    )
    await emit(
        "log_forge",
        {"error_type": "state_update_processing_error", "message": forge},
    )
    await emit(
        "log_forge_dispatch",
        {"error_type": "dispatch_function_missing", "substate": forge},
    )

    # 3. Unknown error_type (falls to else branch)
    await emit(
        "unknown_type",
        {"error_type": "totally_made_up_type\x1b[5m", "message": "hello"},
    )

    # 4. Oversized message: 10MB string. Tests bounding + max_http_buffer_size.
    big = "A" * (10 * 1024 * 1024)
    await emit("oversized_10mb", {"error_type": "state_update_processing_error", "message": big})
    await asyncio.sleep(1.0)
    print(f"STILL_CONNECTED_after_10mb={sio.connected}")

    # 4b. Just-over-500-char message: tests truncation boundary.
    await emit(
        "just_over_500",
        {"error_type": "state_update_processing_error", "message": "B" * 550},
    )

    print(f"CATCHALL_EVENTS={len(results)}")
    for r in results[:20]:
        print(" ", r)

    await sio.disconnect()

    # 5. Flood test: fresh connection, emit many to trip per-sid + per-window
    #    limits. Reconnect loop to also probe per-window bound.
    for round_i in range(4):
        s2 = new_client()
        try:
            await s2.connect(
                f"{backend_url}?token=flood-token-{round_i}",
                socketio_path="_event",
                namespaces=[ns],
                transports=["websocket"],
                wait_timeout=10,
            )
        except Exception as e:  # noqa: BLE001
            print(f"FLOOD round {round_i} connect EXC: {e}")
            continue
        await asyncio.sleep(0.3)
        for i in range(8):
            await s2.emit(
                "client_error",
                {"error_type": "state_update_processing_error", "message": f"flood r{round_i} n{i}"},
                namespace=ns,
            )
        await asyncio.sleep(0.3)
        print(f"FLOOD round {round_i} sent 8 (per-sid cap is 5)")
        await s2.disconnect()

    # 6. Unknown-sid gating: connect WITHOUT a token so sid is not linked.
    s3 = new_client()
    try:
        await s3.connect(
            backend_url,
            socketio_path="_event",
            namespaces=[ns],
            transports=["websocket"],
            wait_timeout=10,
        )
        await asyncio.sleep(0.3)
        await s3.emit(
            "client_error",
            {"error_type": "state_update_processing_error", "message": "from-unlinked-sid"},
            namespace=ns,
        )
        await asyncio.sleep(0.4)
        print("UNLINKED_SID sent (should be debug-level only, not error)")
        await s3.disconnect()
    except Exception as e:  # noqa: BLE001
        print(f"UNLINKED_SID connect EXC: {e}")

    print("DONE")


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "/"))
