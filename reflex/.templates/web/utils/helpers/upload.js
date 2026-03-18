import JSON5 from "json5";
import env from "$/env.json";

const trackUploadResponse = (socket) => {
  // Track how many partial updates have been processed for this upload.
  let resp_idx = 0;

  return (progressEvent) => {
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
};

const sendUploadRequest = async ({
  handler,
  upload_id,
  on_upload_progress,
  extra_headers,
  refs,
  getToken,
  formdata,
  url,
  responseHandler,
}) => {
  const upload_ref_name = `__upload_controllers_${upload_id}`;

  if (refs[upload_ref_name]) {
    return false;
  }

  const controller = new AbortController();

  refs[upload_ref_name] = controller;

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

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

    if (on_upload_progress) {
      xhr.upload.onprogress = function (event) {
        if (event.lengthComputable) {
          on_upload_progress({
            loaded: event.loaded,
            total: event.total,
            progress: event.loaded / event.total,
          });
        }
      };
    }

    if (responseHandler) {
      xhr.onprogress = function (event) {
        responseHandler({
          event: {
            target: {
              responseText: xhr.responseText,
            },
          },
          progress: event.lengthComputable ? event.loaded / event.total : 0,
        });
      };
    }

    controller.signal.addEventListener("abort", () => {
      xhr.abort();
    });

    xhr.open("POST", url);
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

/**
 * Upload files to the server.
 *
 * @param handler The handler to use.
 * @param upload_id The upload id to use.
 * @param on_upload_progress The function to call on upload progress.
 * @param extra_headers Extra headers to send with the request.
 * @param socket The websocket connection.
 * @param refs The refs object to store the abort controller in.
 * @param getBackendURL Function to get the backend URL.
 * @param getToken Function to get the Reflex token.
 *
 * @returns The response from posting to the upload endpoint.
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
  if (files === undefined || files.length === 0) {
    return false;
  }

  const formdata = new FormData();

  files.forEach((file) => {
    formdata.append("files", file, file.path || file.name);
  });

  return sendUploadRequest({
    handler,
    upload_id,
    on_upload_progress,
    extra_headers,
    refs,
    getToken,
    formdata,
    url: getBackendURL(env.UPLOAD),
    responseHandler: trackUploadResponse(socket),
  });
};

/**
 * Upload files to the streaming chunk endpoint.
 *
 * @param handler The handler to use.
 * @param files The files to upload.
 * @param upload_id The upload id to use.
 * @param on_upload_progress The function to call on upload progress.
 * @param extra_headers Extra headers to send with the request.
 * @param _socket The websocket connection.
 * @param refs The refs object to store the abort controller in.
 * @param getBackendURL Function to get the backend URL.
 * @param getToken Function to get the Reflex token.
 *
 * @returns The response from posting to the chunk upload endpoint.
 */
export const uploadFilesChunk = async (
  handler,
  files,
  upload_id,
  on_upload_progress,
  extra_headers,
  _socket,
  refs,
  getBackendURL,
  getToken,
) => {
  if (files === undefined || files.length === 0) {
    return false;
  }

  const formdata = new FormData();

  files.forEach((file) => {
    formdata.append("files", file, file.path || file.name);
  });

  return sendUploadRequest({
    handler,
    upload_id,
    on_upload_progress,
    extra_headers,
    refs,
    getToken,
    formdata,
    url: getBackendURL(env.UPLOAD_CHUNK),
  });
};
