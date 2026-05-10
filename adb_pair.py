#!/usr/bin/env python3
"""Wireless ADB pairing — show QR code, phone scans it, done."""

import os
import random
import socket
import string
import subprocess
import sys
import threading

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
BLUE = "\033[34m"


def ensure_deps():
    for pkg in ("qrcode", "zeroconf"):
        try:
            __import__(pkg)
        except ImportError:
            print(f"{YELLOW}Installing {pkg}...{RESET}")
            args = [sys.executable, "-m", "pip", "install", pkg]
            if sys.platform == "darwin":
                args.append("--break-system-packages")
            subprocess.run(args, check=True, capture_output=True)


def get_local_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except Exception:
            return "unknown"


def print_qr(data: str):
    import qrcode
    qr = qrcode.QRCode(border=1)
    qr.add_data(data)
    qr.make(fit=True)
    qr.print_ascii(invert=True)


def run_adb(args: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(["adb"] + args, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def check_adb():
    if run_adb(["version"])[0] != 0:
        print(f"{RED}✗ adb not found. Install Android platform-tools first.{RESET}")
        print("  brew install --cask android-platform-tools")
        sys.exit(1)


def header():
    os.system("clear")
    print(f"\n{BOLD}{CYAN}  ╔══════════════════════════════╗")
    print(f"  ║  Wireless ADB Pairing Tool   ║")
    print(f"  ╚══════════════════════════════╝{RESET}\n")


def step(n: int, msg: str):
    print(f"\n  {BOLD}{BLUE}[{n}]{RESET} {msg}")


def success(msg: str):
    print(f"\n  {GREEN}{BOLD}✓ {msg}{RESET}")


def error(msg: str):
    print(f"\n  {RED}✗ {msg}{RESET}")


def _random_str(length: int) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def discover_mdns(service_type: str, match_fn, timeout: int) -> dict | None:
    """Generic mDNS browser; returns first result where match_fn(host, port) is truthy."""
    from zeroconf import ServiceBrowser, Zeroconf

    found = threading.Event()
    result: dict = {}

    class Listener:
        def _check(self, zc, type_, name):
            info = zc.get_service_info(type_, name)
            if not info or not info.addresses:
                return
            host = socket.inet_ntoa(info.addresses[0])
            port = info.port
            if match_fn(host, port, name) and not found.is_set():
                result.update(host=host, port=port)
                found.set()

        def add_service(self, zc, type_, name):
            self._check(zc, type_, name)

        def update_service(self, zc, type_, name):
            self._check(zc, type_, name)

        def remove_service(self, zc, type_, name):
            pass

    zc = Zeroconf()
    ServiceBrowser(zc, service_type, Listener())
    try:
        found.wait(timeout=timeout)
    finally:
        zc.close()

    return result or None


def main():
    ensure_deps()
    check_adb()
    header()

    local_ip = get_local_ip()
    print(f"  {DIM}Your machine: {local_ip}{RESET}")

    # QR payload format Android expects for "Pair device with QR code"
    service_name = f"studio-{_random_str(10)}"
    password = _random_str(10)
    qr_data = f"WIFI:T:ADB;S:{service_name};P:{password};;"

    step(1, "On your Android phone:")
    print(f"      Settings → Developer options → Wireless debugging → enable it")
    step(2, f"Tap  {BOLD}\"Pair device with QR code\"{RESET}  and scan this:")
    print()
    print_qr(qr_data)
    print(f"  {DIM}Waiting for phone to appear on the network (up to 2 min)...{RESET}\n")

    # Phone scans QR → advertises _adb-tls-pairing._tcp with our service_name
    pairing = discover_mdns(
        "_adb-tls-pairing._tcp.local.",
        match_fn=lambda host, port, name: service_name in name,
        timeout=120,
    )
    if not pairing:
        error("Timed out. Make sure the phone is on the same Wi-Fi network.")
        sys.exit(1)

    addr = f"{pairing['host']}:{pairing['port']}"
    print(f"  {DIM}Found phone at {addr} — pairing...{RESET}")

    rc, out, err = run_adb(["pair", addr, password])
    combined = (out + err).lower()
    if rc != 0 or "error" in combined or "failed" in combined:
        error(f"Pairing failed: {out or err}")
        sys.exit(1)

    success(f"Paired!  {out}")

    # Phone also advertises _adb-tls-connect._tcp — discover it to auto-connect
    step(3, "Discovering wireless debug port for connection...")
    connect = discover_mdns(
        "_adb-tls-connect._tcp.local.",
        match_fn=lambda host, port, name: host == pairing["host"],
        timeout=30,
    )

    if connect:
        connect_addr = f"{connect['host']}:{connect['port']}"
        print(f"  {DIM}Connecting to {connect_addr}...{RESET}")
        rc, out, err = run_adb(["connect", connect_addr])
        if "connected" in (out + err).lower():
            success(f"Connected!  {out}")
            print(f"  {DIM}To reconnect later:  adb connect {connect_addr}{RESET}")
        else:
            error(f"Connection failed: {out or err}")
    else:
        print(f"\n  {YELLOW}Could not auto-discover connect port.{RESET}")
        print(f"  On your phone, note the IP:port on the Wireless debugging screen and run:")
        print(f"  {BOLD}    adb connect {pairing['host']}:<port>{RESET}")

    print(f"\n  {DIM}Current adb devices:{RESET}")
    _, out, _ = run_adb(["devices", "-l"])
    for line in out.splitlines():
        print(f"    {line}")

    print(f"\n  {GREEN}All done!{RESET}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {DIM}Cancelled.{RESET}\n")
        sys.exit(0)
