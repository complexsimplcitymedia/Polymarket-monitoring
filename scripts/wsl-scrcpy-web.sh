#!/usr/bin/env bash
# Run ON wolf-wsl-ubuntu (100.110.82.182) - the WSL side where the phone attaches.
# Mirrors the S24 Ultra (or any USB/wifi-connected Android) to a browser-viewable stream
# reachable from the whole tailnet. Then put http://<WSL-tailnet-ip>:8000/ into WATCH_URL.
set -e
WSL_IP=$(tailscale ip -4 | head -1)
echo "WSL tailnet IP: ${WSL_IP}"
mkdir -p ~/scrcpy-web && cd ~/scrcpy-web
# adb 32-bit deps + scrcpy server assets are bundled in the image
docker rm -f ws-scrcpy 2>/dev/null || true
docker run -d --name ws-scrcpy \
  -p 8000:8000 \
  -v /dev/bus/usb:/dev/bus/usb \
  --device-cgroup-rule='c 189:* rmw' \
  scavin/ws-scrcpy:latest
echo "Mirror UI:  http://${WSL_IP}:8000/"
echo "Connect the phone via USB then click your device in the ws-scrcpy web UI (H.264 > scrcpy)."
echo "Phone wireless option: enable wireless debugging on the phone, adb connect <phone-ip>:<port> in the UI."
