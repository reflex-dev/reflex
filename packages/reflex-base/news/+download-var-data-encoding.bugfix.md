`rx.download(data=State.var)` percent-encodes the JSON it puts in the `data:` URL, so a `#` or `%` in the data no longer truncates or corrupts the downloaded file.
