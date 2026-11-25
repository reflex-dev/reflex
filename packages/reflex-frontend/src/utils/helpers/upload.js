import env from "$/env.json";
import { parseJson } from "$/utils/helpers/json";

/**
 * Upload files to the server.
 *
 * @param state The state to apply the delta to.
 * @param handler The handler to use.
 * @param upload_id The upload id to use.
 * @param on_upload_progress The function to call on upload progress.
 * @param extra_headers Extra headers to send with the request.
 * @param extra_args Extra bound handler args to forward to the backend handler.
 * @param socket the websocket connection
 * @param refs The refs object to store the abort controller in.
 * @param getBackendURL Function to get the backend URL.
 * @param getToken Function to get the Reflex token.
 * @param waitForSession Wait for the session cookie before starting HTTP traffic.
 * @param devMode Whether the app runs in development mode.
 *
 * @returns The response from posting to the UPLOADURL endpoint.
 */
export const uploadFiles = async (
  handler,
  files,
  upload_id,
  on_upload_progress,
  extra_headers,
  extra_args,
  socket,
  refs,
  getBackendURL,
  getToken,
  waitForSession,
  devMode,
) => {
  files = files ?? [];

  const upload_ref_name = `__upload_controllers_${upload_id}`;

  if (refs[upload_ref_name]) {
    console.log("Upload already in progress for ", upload_id);
    return false;
  }

  const controller = new AbortController();
  refs[upload_ref_name] = controller;
  if (waitForSession) {
    let abortWaiting;
    const cancelled = new Promise((resolve) => {
      abortWaiting = resolve;
      controller.signal.addEventListener("abort", abortWaiting, { once: true });
    });
    try {
      await Promise.race([waitForSession(), cancelled]);
    } catch (error) {
      console.log("Upload session error:", error.message);
      delete refs[upload_ref_name];
      return false;
    } finally {
      controller.signal.removeEventListener("abort", abortWaiting);
    }
  }
  if (controller.signal.aborted || !socket.connected) {
    delete refs[upload_ref_name];
    return false;
  }

  // Track how many partial updates have been processed for this upload.
  let resp_idx = 0;
  // Set when the server ends the stream with an error frame (handler raised).
  let stream_error;
  const eventHandler = (responseText, complete = false) => {
    const event_callbacks = socket._callbacks.$event;
    // Whenever called, responseText will contain the entire response so far.
    const response = responseText.trim();
    if (!response) {
      return;
    }
    const chunks = response.split("\n");
    // So only process _new_ chunks beyond resp_idx.
    for (const chunk_json of chunks.slice(resp_idx)) {
      let chunk;
      try {
        chunk = parseJson(chunk_json);
      } catch (e) {
        // The last chunk may be incomplete; the next progress event parses it
        // again, so only report errors when the full response is available.
        if (complete) {
          console.log("Error parsing chunk", chunk_json, e);
        }
        return;
      }
      // Mark this chunk as processed before it is handled, so no later
      // progress event handles it again, whether the listener is sync or async.
      resp_idx += 1;
      if (chunk.error !== undefined) {
        stream_error = chunk.error;
        continue;
      }
      for (const f of event_callbacks) {
        // f runs right away; a failure, thrown or rejected, is reported.
        (async () => f(chunk))().catch((e) =>
          console.log("Error processing chunk", chunk, e),
        );
      }
    }
  };

  const formdata = new FormData();

  // Bound handler args are sent as a JSON form field that must precede the
  // files, so the streaming chunk parser reads it before the first file part.
  // Field name kept in sync with UPLOAD_EVENT_ARGS_FIELD in _upload.py.
  if (extra_args && Object.keys(extra_args).length > 0) {
    formdata.append("__reflex_event_args", JSON.stringify(extra_args));
  }

  // Add the token and handler to the file name.
  files.forEach((file) => {
    formdata.append("files", file, file.path || file.name);
  });

  // Send the file to the server.

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    // Set up event handlers
    xhr.onload = function () {
      const ok = xhr.status >= 200 && xhr.status < 300;
      if (ok) {
        eventHandler(xhr.responseText, true);
      }
      if (stream_error !== undefined) {
        reject(new Error(stream_error));
      } else if (ok) {
        resolve({
          data: xhr.responseText,
          status: xhr.status,
          statusText: xhr.statusText,
          headers: {
            get: (name) => xhr.getResponseHeader(name),
          },
        });
      } else {
        /** @type {Error & { rejection?: string }} */
        const error = new Error(`HTTP error! status: ${xhr.status}`);
        if (xhr.status >= 400 && xhr.status < 500) {
          // The server refused the request before the event handler ran, so
          // no backend error reaches the page for it. Only development shows
          // the server's own words, as for a failed event handler.
          if (devMode) {
            error.rejection = `The server rejected the upload (${xhr.status}): ${xhr.responseText.slice(0, 200)}`;
          } else if (xhr.status === 403) {
            error.rejection =
              "Your session has expired. Reload the page and try again.";
          } else {
            error.rejection = "The server rejected the upload.";
          }
        }
        reject(error);
      }
    };

    xhr.onerror = function () {
      reject(new Error("Network error"));
    };

    xhr.onabort = function () {
      reject(new Error("Upload aborted"));
    };

    // Handle upload progress
    if (on_upload_progress) {
      xhr.upload.onprogress = function (event) {
        if (event.lengthComputable) {
          const progressEvent = {
            loaded: event.loaded,
            total: event.total,
            progress: event.loaded / event.total,
          };
          on_upload_progress(progressEvent);
        }
      };
    }

    // Handle download progress with streaming response parsing
    xhr.onprogress = function () {
      // Only a 2xx body is an update stream; onload reports an error status.
      if (xhr.status < 200 || xhr.status >= 300) return;
      eventHandler(xhr.responseText);
    };

    // Handle abort controller
    controller.signal.addEventListener("abort", () => {
      xhr.abort();
    });

    // Configure and send request
    xhr.open("POST", getBackendURL(env.UPLOAD));
    xhr.withCredentials = true;
    xhr.setRequestHeader("Reflex-Client-Token", getToken());
    xhr.setRequestHeader("Reflex-Event-Handler", handler);
    // Instrumentation hook (installed by reflex-otel): may add trace headers.
    /** @type {Record<string, string>} */
    const trace_headers = {};
    window.__reflex_otel?.onUploadSend?.(handler, trace_headers);
    for (const [key, value] of Object.entries(trace_headers)) {
      xhr.setRequestHeader(key, value);
    }
    for (const [key, value] of Object.entries(extra_headers || {})) {
      xhr.setRequestHeader(key, value);
    }

    try {
      xhr.send(formdata);
    } catch (error) {
      reject(error);
    }
  })
    .catch((error) => {
      console.log("Upload error:", error.message);
      if (error.rejection) {
        // Show it as a failed event handler is shown: a toast, or an alert
        // when the app has no toast provider.
        if (refs.__toast) {
          refs.__toast.error("Upload failed.", {
            description: error.rejection,
            position: "top-center",
            id: "upload_error",
          });
        } else {
          window.alert(`Upload failed. ${error.rejection}`);
        }
      }
      return false;
    })
    .finally(() => {
      delete refs[upload_ref_name];
    });
};
