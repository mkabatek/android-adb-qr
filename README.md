# android-adb-qr

Pair your Android phone to ADB over Wi-Fi by scanning a QR code — no USB cable needed.

## What it does

1. Generates a QR code in the terminal using Android's `WIFI:T:ADB;...` pairing format
2. You scan it on your phone via **Settings → Developer options → Wireless debugging → Pair device with QR code**
3. The script listens on the local network via mDNS for the phone to advertise itself after scanning
4. Automatically runs `adb pair` with the discovered address and password
5. Then discovers the connect port and runs `adb connect` so the device is ready to use immediately

## Requirements

- Python 3.10+
- [`adb`](https://developer.android.com/tools/adb) (Android platform-tools) on your `PATH`
- Android 11+ with **Wireless debugging** enabled in Developer options
- Your Mac and phone on the **same Wi-Fi network**

Install platform-tools:

**macOS**
```sh
brew install --cask android-platform-tools
```

**Windows**

Download and extract the [Android platform-tools ZIP](https://developer.android.com/tools/releases/platform-tools) from Google, then add the extracted folder to your `PATH`, or run `adb` from that folder directly.

**Linux**
```sh
# Debian/Ubuntu
sudo apt install adb

# Arch
sudo pacman -S android-tools

# Fedora
sudo dnf install android-tools
```

Python dependencies (`qrcode`, `zeroconf`) are installed automatically on first run if missing.

## Usage

```sh
python3 adb_pair.py
```

Follow the on-screen instructions. The whole flow takes about 10–15 seconds once the QR code is scanned.

## How it works

Android's wireless debugging pairing encodes the session credentials in a QR code with the format:

```
WIFI:T:ADB;S:<service-name>;P:<password>;;
```

After the phone scans the code, it advertises a pairing service over mDNS (`_adb-tls-pairing._tcp.local.`). The script uses [zeroconf](https://pypi.org/project/zeroconf/) to browse for that service, matches it by service name, and completes the TLS pairing handshake via `adb pair`. It then browses for the connect service (`_adb-tls-connect._tcp.local.`) to automatically run `adb connect`.
