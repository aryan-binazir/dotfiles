#!/bin/bash

if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    cat <<'EOF'
check-keyd.sh — verify keyd is running and makima isn't conflicting

We disabled Omarchy's makima service because we wanted caps2esc
functionality via keyd. This script checks that keyd is active/enabled
and warns if makima is still running or enabled (since it conflicts
with keyd). The one thing makima provided that we still want is
handled elsewhere — this just guards the keyd setup.

Usage: check-keyd.sh [--help]
EOF
    exit 0
fi

keyd_active=$(systemctl is-active keyd)
keyd_enabled=$(systemctl is-enabled keyd)
makima_active=$(systemctl is-active makima)
makima_enabled=$(systemctl is-enabled makima)

echo "keyd:   $keyd_active / $keyd_enabled"
echo "makima: $makima_active / $makima_enabled"
[[ "$makima_active" == "active" ]] && echo "WARNING: makima is running — conflicts with keyd!"
[[ "$makima_enabled" == "enabled" ]] && echo "WARNING: makima is enabled — will conflict on reboot!"
