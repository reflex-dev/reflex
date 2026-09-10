#!/usr/bin/env bash
# Raw-byte check of the Safari cache-bust rewrite with curl against a running dev server.
# usage: curl_safari.sh <base_url> <out_dir>
URL=$1; OUT=$2; mkdir -p "$OUT"
SAFARI='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15'
CHROME='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
for route in "" about long; do
  for ua in safari chrome; do
    if [ $ua = safari ]; then A="$SAFARI"; else A="$CHROME"; fi
    name="curl_${ua}_${route:-index}"
    curl -s --noproxy '*' -A "$A" -H 'Accept: text/html,application/xhtml+xml' -D "$OUT/$name.headers" -o "$OUT/$name.html" "$URL/$route"
    printf '%-22s bytes=%-6s ' "$name" "$(stat -c %s "$OUT/$name.html")"
    printf 'x-modified-by=%s ' "$(grep -i '^x-modified-by' "$OUT/$name.headers" | tr -d '\r' | cut -d' ' -f2)"
    printf 'transfer=%s ' "$(grep -i '^transfer-encoding' "$OUT/$name.headers" | tr -d '\r' | cut -d' ' -f2)"
    printf 'reflex_ts=%s ' "$(grep -o '__reflex_ts=[0-9]*' "$OUT/$name.html" | wc -l)"
    printf 'byte-list=%s ' "$(head -c 200 "$OUT/$name.html" | grep -cE '^[0-9]{1,3},[0-9]{1,3},[0-9]{1,3},')"
    printf 'utf8-valid=%s ' "$(iconv -f UTF-8 -t UTF-8 "$OUT/$name.html" >/dev/null 2>&1 && echo yes || echo NO)"
    printf 'fffd=%s ' "$(grep -c $'\xef\xbf\xbd' "$OUT/$name.html")"
    printf 'nihongo=%s\n' "$(grep -o '日本語' "$OUT/$name.html" | wc -l)"
  done
done
echo "--- first 120 bytes of the Safari /long response (hexdump):"; head -c 120 "$OUT/curl_safari_long.html" | od -c | head -8
echo "--- head of the Safari /long response (text):"; head -c 420 "$OUT/curl_safari_long.html"; echo
echo "--- diff safari vs chrome after stripping the param (/long):"
diff <(sed -E 's/[?&]__reflex_ts=[0-9]+//g' "$OUT/curl_safari_long.html") "$OUT/curl_chrome_long.html" >/dev/null && echo IDENTICAL || echo DIFFERENT
