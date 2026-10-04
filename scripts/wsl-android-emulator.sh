#!/usr/bin/env bash
# Run on wolf-wsl-ubuntu (100.110.82.182): spin up android_emulator_11.0 (budtmo/docker-android)
# Web screen (noVNC): http://<WSL-tailnet-ip>:6080   |  ADB: <WSL-tailnet-ip>:5555
set -e
TS_IP=$(tailscale ip -4 | head -1)
docker rm -f android_emulator_11.0 2>/dev/null || true
docker run -d --name android_emulator_11.0 \
  -e DEVICE="Samsung Galaxy S24 Ultra" \
  -e DISPLAY=:6080 \
  -p 5554:5555 -p 6080:6080 \
  --memory=4g --cpus=4 \
  budtmo/docker-android:latest
echo "VNC/web UI: http://${TS_IP}:6080/"
echo "ADB target: ${TS_IP}:5555  (adb connect from any tailnet machine)"
echo "Install MLB app from Play Store inside the emulator, log in once, done."
