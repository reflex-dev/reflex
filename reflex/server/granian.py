
from dataclasses import dataclass

from reflex.server.base import CustomBackendServer

@dataclass
class HTTP1Settings:  # https://github.com/emmett-framework/granian/blob/261ceba3fd93bca10300e91d1498bee6df9e3576/granian/http.py#L6
    keep_alive: bool = True
    max_buffer_size: int = 8192 + 4096 * 100
    pipeline_flush: bool = False


@dataclass
class HTTP2Settings:  # https://github.com/emmett-framework/granian/blob/261ceba3fd93bca10300e91d1498bee6df9e3576/granian/http.py#L13
    adaptive_window: bool = False
    initial_connection_window_size: int = 1024 * 1024
    initial_stream_window_size: int = 1024 * 1024
    keep_alive_interval: int | None = None
    keep_alive_timeout: int = 20
    max_concurrent_streams: int = 200
    max_frame_size: int = 1024 * 16
    max_headers_size: int = 16 * 1024 * 1024
    max_send_buffer_size: int = 1024 * 400

try:
    import watchfiles
except ImportError:
    watchfiles = None

class GranianBackendServer(CustomBackendServer):

    def run_prod(self):
        pass

    def run_dev(self):
        pass
