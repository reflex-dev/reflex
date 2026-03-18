import JSON5 from "json5";
import env from "$/env.json";

const UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024;
const logUpload = (message, details = {}) => {
  console.log(`[reflex upload] ${message}`, details);
};

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
    logUpload("upload already in progress", { upload_id, handler });
    return false;
  }

  const controller = new AbortController();

  refs[upload_ref_name] = controller;

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    logUpload("sending request", {
      handler,
      upload_id,
      url: String(url),
      request_kind: responseHandler ? "classic" : "chunked",
    });

    xhr.onload = function () {
      if (xhr.status >= 200 && xhr.status < 300) {
        logUpload("request completed", {
          handler,
          upload_id,
          status: xhr.status,
          response_length: xhr.responseText.length,
        });
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
      logUpload("request failed", { handler, upload_id });
      reject(new Error("Network error"));
    };

    xhr.onabort = function () {
      logUpload("request aborted", { handler, upload_id });
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

const createChunkUploadController = () => ({
  cancelled: false,
  currentXhr: null,
  abort() {
    this.cancelled = true;
    this.currentXhr?.abort();
  },
});

const createChunkUploadSessionId = () => {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return `upload-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const buildChunkUploadURL = ({
  getBackendURL,
  sessionId,
  upload_id,
  filename,
  offset,
  complete = false,
  cancel = false,
}) => {
  const url = new URL(getBackendURL(env.UPLOAD_CHUNK));
  const searchParams = new URLSearchParams({
    session_id: sessionId,
  });

  if (upload_id) {
    searchParams.set("upload_id", upload_id);
  }
  if (filename !== undefined) {
    searchParams.set("filename", filename);
  }
  if (offset !== undefined) {
    searchParams.set("offset", String(offset));
  }
  if (complete) {
    searchParams.set("complete", "1");
  }
  if (cancel) {
    searchParams.set("cancel", "1");
  }

  url.search = searchParams.toString();
  return url;
};

const sendChunkUploadRequest = async ({
  handler,
  upload_id,
  extra_headers,
  getToken,
  url,
  body,
  contentType,
  controller,
  onRequestProgress,
  details,
}) =>
  new Promise((resolve, reject) => {
    if (controller.cancelled) {
      reject(new Error("Upload aborted"));
      return;
    }

    const xhr = new XMLHttpRequest();
    const cleanup = () => {
      if (controller.currentXhr === xhr) {
        controller.currentXhr = null;
      }
    };
    controller.currentXhr = xhr;

    logUpload("sending request", {
      handler,
      upload_id,
      url: String(url),
      request_kind: "chunked",
      ...details,
    });

    xhr.onload = function () {
      cleanup();
      if (xhr.status >= 200 && xhr.status < 300) {
        logUpload("request completed", {
          handler,
          upload_id,
          status: xhr.status,
          response_length: xhr.responseText.length,
          ...details,
        });
        resolve(xhr.status);
      } else {
        reject(new Error(`HTTP error! status: ${xhr.status}`));
      }
    };

    xhr.onerror = function () {
      cleanup();
      logUpload("request failed", { handler, upload_id, ...details });
      reject(new Error("Network error"));
    };

    xhr.onabort = function () {
      cleanup();
      logUpload("request aborted", { handler, upload_id, ...details });
      reject(new Error("Upload aborted"));
    };

    if (onRequestProgress) {
      xhr.upload.onprogress = function (event) {
        onRequestProgress(event);
      };
    }

    xhr.open("POST", url);
    xhr.setRequestHeader("Reflex-Client-Token", getToken());
    xhr.setRequestHeader("Reflex-Event-Handler", handler);
    if (contentType) {
      xhr.setRequestHeader("Content-Type", contentType);
    }
    for (const [key, value] of Object.entries(extra_headers || {})) {
      xhr.setRequestHeader(key, value);
    }

    try {
      xhr.send(body);
    } catch (error) {
      cleanup();
      reject(error);
    }
  });

const notifyChunkUploadCancelled = async ({
  handler,
  upload_id,
  sessionId,
  extra_headers,
  getBackendURL,
  getToken,
}) => {
  const url = buildChunkUploadURL({
    getBackendURL,
    sessionId,
    upload_id,
    cancel: true,
  });

  logUpload("sending cancel request", {
    handler,
    upload_id,
    session_id: sessionId,
    url: String(url),
  });

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Reflex-Client-Token": getToken(),
        "Reflex-Event-Handler": handler,
        ...extra_headers,
      },
      keepalive: true,
    });
    logUpload("cancel request completed", {
      handler,
      upload_id,
      session_id: sessionId,
      status: response.status,
    });
  } catch (error) {
    logUpload("cancel request failed", {
      handler,
      upload_id,
      session_id: sessionId,
      error: error.message,
    });
  }
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
    logUpload("classic upload skipped because there are no files", {
      handler,
      upload_id,
    });
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
    logUpload("chunked upload skipped because there are no files", {
      handler,
      upload_id,
    });
    return false;
  }

  const maxSize = Math.max(...files.map((file) => file.size), 0);
  const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
  const totalRequestCount = files.reduce(
    (sum, file) => sum + Math.max(1, Math.ceil(file.size / UPLOAD_CHUNK_SIZE)),
    0,
  );
  const upload_ref_name = `__upload_controllers_${upload_id}`;

  if (refs[upload_ref_name]) {
    logUpload("upload already in progress", { upload_id, handler });
    return false;
  }

  const controller = createChunkUploadController();
  const sessionId = createChunkUploadSessionId();
  refs[upload_ref_name] = controller;

  logUpload("prepared chunked upload plan", {
    handler,
    upload_id,
    session_id: sessionId,
    file_count: files.length,
    max_file_size: maxSize,
    total_size: totalBytes,
    chunk_size: UPLOAD_CHUNK_SIZE,
    request_count: totalRequestCount,
    files: files.map((file) => ({
      name: file.path || file.name,
      size: file.size,
      type: file.type,
    })),
  });

  let uploadedBytes = 0;
  let requestIndex = 0;
  let completed = false;
  const maxIterations = Math.max(maxSize, 1);

  try {
    for (let offset = 0; offset < maxIterations; offset += UPLOAD_CHUNK_SIZE) {
      for (const file of files) {
        if (controller.cancelled) {
          throw new Error("Upload aborted");
        }

        const filename = file.path || file.name;
        let chunkBlob;
        if (file.size === 0) {
          if (offset !== 0) {
            continue;
          }
          chunkBlob = file.slice(0, 0, file.type);
        } else {
          if (offset >= file.size) {
            continue;
          }
          chunkBlob = file.slice(offset, offset + UPLOAD_CHUNK_SIZE, file.type);
        }

        const isFinalRequest = requestIndex === totalRequestCount - 1;
        const url = buildChunkUploadURL({
          getBackendURL,
          sessionId,
          upload_id,
          filename,
          offset,
          complete: isFinalRequest,
        });

        await sendChunkUploadRequest({
          handler,
          upload_id,
          extra_headers,
          getToken,
          url,
          body: chunkBlob,
          contentType:
            chunkBlob.type || file.type || "application/octet-stream",
          controller,
          details: {
            session_id: sessionId,
            file_name: filename,
            offset,
            request_index: requestIndex,
            complete: isFinalRequest,
          },
          onRequestProgress: (event) => {
            if (!on_upload_progress || !event.lengthComputable) {
              return;
            }
            const loaded = uploadedBytes + event.loaded;
            const total = totalBytes;
            on_upload_progress({
              loaded,
              total,
              progress: total === 0 ? 1 : loaded / total,
            });
          },
        });

        uploadedBytes += chunkBlob.size;
        requestIndex += 1;
      }
    }

    if (on_upload_progress) {
      on_upload_progress({
        loaded: totalBytes,
        total: totalBytes,
        progress: 1,
      });
    }
    completed = true;
    return true;
  } catch (error) {
    console.log("Upload error:", error.message);
    return false;
  } finally {
    if (!completed && requestIndex > 0) {
      await notifyChunkUploadCancelled({
        handler,
        upload_id,
        sessionId,
        extra_headers,
        getBackendURL,
        getToken,
      });
    }
    delete refs[upload_ref_name];
  }
};
