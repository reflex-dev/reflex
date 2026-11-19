File uploads now log an update chunk that fails to parse once the upload response completes. Before, the error was logged only when the response had a `Content-Length` header.
