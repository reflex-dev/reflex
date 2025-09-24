import JSON5 from "json5";
import env from "$/env.json";

/**
 * Upload files to the server.
 *
 * @param state The state to apply the delta to.
 * @param handler The handler to use.
 * @param upload_id The upload id to use.
 * @param on_upload_progress The function to call on upload progress.
 * @param socket the websocket connection
 * @param extra_headers Extra headers to send with the request.
 * @param refs The refs object to store the abort controller in.
 * @param getBackendURL Function to get the backend URL.
 * @param getToken Function to get the Reflex token.
 *
 * @returns The response from posting to the UPLOADURL endpoint.
 */
export const uploadFiles = async (
  handler,
  files,
  upload_id,
  on_upload_progress,
  extra_headers,
  socket,
  refs,
  getBackendURL,
  getToken,
) => {
  // return if there's no file to upload
  if (files === undefined || files.length === 0) {
    return false;
  }

  const upload_ref_name = `__upload_controllers_${upload_id}`;

  if (refs[upload_ref_name]) {
    console.log("Upload already in progress for ", upload_id);
    return false;
  }

  // Track how many partial updates have been processed for this upload.
  let resp_idx = 0;
  const eventHandler = (progressEvent) => {
    const event_callbacks = socket._callbacks.$event;
    // Whenever called, responseText will contain the entire response so far.
    const chunks = progressEvent.event.target.responseText.trim().split("\n");
    // So only process _new_ chunks beyond resp_idx.
    chunks.slice(resp_idx).map((chunk_json) => {
      try {
        const chunk = JSON5.parse(chunk_json);
        event_callbacks.map((f, ix) => {
          f(chunk)
            .then(() => {
              if (ix === event_callbacks.length - 1) {
                // Mark this chunk as processed.
                resp_idx += 1;
              }
            })
            .catch((e) => {
              if (progressEvent.progress === 1) {
                // Chunk may be incomplete, so only report errors when full response is available.
                console.log("Error processing chunk", chunk, e);
              }
              return;
            });
        });
      } catch (e) {
        if (progressEvent.progress === 1) {
          console.log("Error parsing chunk", chunk_json, e);
        }
        return;
      }
    });
  };

  const controller = new AbortController();
  const formdata = new FormData();

  // Add the token and handler to the file name.
  files.forEach((file) => {
    formdata.append("files", file, file.path || file.name);
  });

  // Send the file to the server.
  refs[upload_ref_name] = controller;

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    // Set up event handlers
    xhr.onload = function () {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve({
          data: xhr.responseText,
          status: xhr.status,
          statusText: xhr.statusText,
          headers: {
            get: (name) => xhr.getResponseHeader(name),
          },
        });
      } else {
        reject(new Error(`HTTP error! status: ${xhr.status}`));
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
    xhr.onprogress = function (event) {
      if (eventHandler) {
        const progressEvent = {
          event: {
            target: {
              responseText: xhr.responseText,
            },
          },
          progress: event.lengthComputable ? event.loaded / event.total : 0,
        };
        eventHandler(progressEvent);
      }
    };

    // Handle abort controller
    controller.signal.addEventListener("abort", () => {
      xhr.abort();
    });

    // Configure and send request
    xhr.open("POST", getBackendURL(env.UPLOAD));
    xhr.setRequestHeader("Reflex-Client-Token", getToken());
    xhr.setRequestHeader("Reflex-Event-Handler", handler);
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
      return false;
    })
    .finally(() => {
      delete refs[upload_ref_name];
    });
};
