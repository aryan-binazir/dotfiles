#!/usr/bin/env bash
set -euo pipefail

CONFIG=/etc/iwd/main.conf
BACKUP_DIR=/etc/iwd/backups
RESTART=1

usage() {
  cat <<'EOF'
Usage: sudo ~/undo-iwd-5ghz-preference.sh [--no-restart]

Removes the iwd 5 GHz preference added via:

  [Rank]
  BandModifier2_4GHz=0.25
  BandModifier5GHz=4.0

If the [Rank] section becomes empty, it removes that section too. By default,
it restarts iwd and systemd-networkd, which briefly disconnects Wi-Fi.
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
  echo "Run this with sudo: sudo ~/undo-iwd-5ghz-preference.sh" >&2
  exit 1
fi

if [[ ! -f "$CONFIG" ]]; then
  echo "$CONFIG does not exist; nothing to undo." >&2
  exit 0
fi

install -d -m 0755 "$BACKUP_DIR"
backup="$BACKUP_DIR/main.conf.before-undo-5ghz.$(date +%Y%m%d-%H%M%S).bak"
cp -a "$CONFIG" "$backup"
echo "Backed up current config to $backup"

tmp=$(mktemp)
awk '
  function flush_rank(  i) {
    if (!in_rank) {
      return
    }
    if (rank_keep_count > 0) {
      print "[Rank]"
      for (i = 1; i <= rank_keep_count; i++) {
        print rank_keep[i]
      }
    }
    in_rank = 0
    rank_keep_count = 0
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
  }
' "$CONFIG" > "$tmp"

install -m 0644 "$tmp" "$CONFIG"
rm -f "$tmp"

echo "Removed iwd 5 GHz preference from $CONFIG."
echo
echo "Current config:"
sed -n '1,120p' "$CONFIG"

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
echo "Current Wi-Fi link:"
iw dev wlan0 link 2>/dev/null || true
