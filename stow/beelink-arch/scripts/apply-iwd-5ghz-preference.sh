#!/usr/bin/env bash
set -euo pipefail

CONFIG=/etc/iwd/main.conf
BACKUP_DIR=/etc/iwd/backups
RESTART=1

usage() {
  cat <<'EOF'
Usage: sudo ~/apply-iwd-5ghz-preference.sh [--no-restart]

Adds or updates this iwd band preference:

  [Rank]
  BandModifier2_4GHz=0.25
  BandModifier5GHz=4.0

This biases iwd toward 5 GHz while keeping 2.4 GHz available as fallback.
By default, it restarts iwd and systemd-networkd, which briefly disconnects
Wi-Fi. To undo, run:

  sudo ~/undo-iwd-5ghz-preference.sh
EOF
}

for arg in "$@"; do
  case "$arg" in
    --no-restart)
      RESTART=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this with sudo: sudo ~/apply-iwd-5ghz-preference.sh" >&2
  exit 1
fi

install -d -m 0755 /etc/iwd "$BACKUP_DIR"

if [[ -f "$CONFIG" ]]; then
  backup="$BACKUP_DIR/main.conf.before-5ghz-preference.$(date +%Y%m%d-%H%M%S).bak"
  cp -a "$CONFIG" "$backup"
  echo "Backed up current config to $backup"
else
  : > "$CONFIG"
  chmod 0644 "$CONFIG"
fi

tmp=$(mktemp)
awk '
  function flush_rank(  i) {
    if (!in_rank) {
      return
    }
    print "[Rank]"
    for (i = 1; i <= rank_keep_count; i++) {
      print rank_keep[i]
    }
    print "BandModifier2_4GHz=0.25"
    print "BandModifier5GHz=4.0"
    in_rank = 0
    rank_keep_count = 0
    saw_rank = 1
    delete rank_keep
  }

  /^[[:space:]]*\[Rank\][[:space:]]*$/ {
    flush_rank()
    in_rank = 1
    next
  }

  /^[[:space:]]*\[[^]]+\][[:space:]]*$/ {
    flush_rank()
    print
    next
  }

  in_rank {
    if ($0 ~ /^[[:space:]]*BandModifier2_4GHz[[:space:]]*=/) {
      next
    }
    if ($0 ~ /^[[:space:]]*BandModifier5GHz[[:space:]]*=/) {
      next
    }
    if ($0 ~ /^[[:space:]]*$/ && rank_keep_count == 0) {
      next
    }
    rank_keep[++rank_keep_count] = $0
    next
  }

  { print }

  END {
    flush_rank()
    if (!saw_rank) {
      if (NR > 0) {
        print ""
      }
      print "[Rank]"
      print "BandModifier2_4GHz=0.25"
      print "BandModifier5GHz=4.0"
    }
  }
' "$CONFIG" > "$tmp"

install -m 0644 "$tmp" "$CONFIG"
rm -f "$tmp"

echo "Installed iwd 5 GHz preference in $CONFIG:"
sed -n '1,140p' "$CONFIG"

if [[ "$RESTART" -eq 0 ]]; then
  echo
  echo "Not restarting services because --no-restart was passed."
  echo "Apply later with: sudo systemctl restart iwd systemd-networkd"
  exit 0
fi

echo
echo "Restarting iwd and systemd-networkd. Wi-Fi will briefly disconnect."
systemctl restart iwd systemd-networkd

echo
echo "Waiting for wlan0 to reconnect..."
for _ in {1..30}; do
  if iw dev wlan0 link 2>/dev/null | grep -q '^Connected to '; then
    break
  fi
  sleep 1
done

echo
echo "Current Wi-Fi link:"
iw dev wlan0 link 2>/dev/null || true
