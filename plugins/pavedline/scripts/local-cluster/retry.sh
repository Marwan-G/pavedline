# shellcheck shell=bash
# Sourced by up.sh. retry <command...>: run a network step again when it fails (a chart or image download can fail
# for a moment: a 504 from a release host, a dropped connection). Attempts and the first delay can be overridden with
# PAVEDLINE_RETRY_ATTEMPTS (default 4) and PAVEDLINE_RETRY_DELAY in seconds (default 15, doubling each time).
retry() {
  local attempts="${PAVEDLINE_RETRY_ATTEMPTS:-4}" delay="${PAVEDLINE_RETRY_DELAY:-15}" n=1
  if ! [[ "$attempts" =~ ^[1-9][0-9]*$ && "$delay" =~ ^[0-9]+$ ]]; then
    echo "error: PAVEDLINE_RETRY_ATTEMPTS must be a positive integer and PAVEDLINE_RETRY_DELAY a whole number" >&2
    return 2
  fi
  until "$@"; do
    if [ "$n" -ge "$attempts" ]; then
      echo "error: failed after $attempts attempts: $*" >&2
      echo "This is usually a network problem. When the network is back, re-run up.sh; it reuses what is already done." >&2
      return 1
    fi
    echo "attempt $n of $attempts failed; retrying in ${delay}s: $*" >&2
    sleep "$delay"
    n=$((n + 1))
    delay=$((delay * 2))
  done
}
