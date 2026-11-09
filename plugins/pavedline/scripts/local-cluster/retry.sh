# shellcheck shell=bash
# Sourced by up.sh. retry <command...>: run a network step again when it fails (a chart or image download can fail
# for a moment: a 504 from a release host, a dropped connection). Attempts and the first delay can be overridden with
# PAVEDLINE_RETRY_ATTEMPTS (default 4) and PAVEDLINE_RETRY_DELAY in seconds (default 15, doubling each time).
retry() {
  local attempts="${PAVEDLINE_RETRY_ATTEMPTS:-4}" delay="${PAVEDLINE_RETRY_DELAY:-15}" n=1
  # No leading zeros (bash would read them as octal) and small bounds (no arithmetic overflow).
  if ! [[ "$attempts" =~ ^[1-9][0-9]?$ && "$delay" =~ ^(0|[1-9][0-9]{0,3})$ ]]; then
    echo "error: PAVEDLINE_RETRY_ATTEMPTS must be 1-99 and PAVEDLINE_RETRY_DELAY 0-9999 seconds, without leading zeros" >&2
    return 2
  fi
  until "$@"; do
    if [ "$n" -ge "$attempts" ]; then
      echo "error: failed after $attempts attempts: $*" >&2
      echo "read the error above. If it was a download or network failure, re-run ${RETRY_SCRIPT:-up.sh} when the network is back; it reuses what is already done." >&2
      return 1
    fi
    echo "attempt $n of $attempts failed; retrying in ${delay}s: $*" >&2
    sleep "$delay"
    n=$((n + 1))
    delay=$((delay * 2))
  done
}
