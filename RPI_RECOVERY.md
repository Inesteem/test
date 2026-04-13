# RPi Recovery Guide (LAN Cable)

If the RPi shows a login screen instead of auto-booting to the desktop,
or the desktop looks broken (no taskbar, black screen), follow these steps.

## What you need

- Ethernet cable connecting your laptop directly to the RPi
- Keyboard attached to the RPi (or accessible via the touchscreen TTY)

## Step 1: Get a network connection

On the RPi screen, switch to a text console:

    Ctrl+Alt+F2

Log in:

    User: pi
    Password: VeryCoolBuzzers!2025

Give the RPi an IP on the ethernet cable:

    sudo ip addr add 169.254.1.2/24 dev eth0

## Step 2: Set up the laptop side

On your laptop, open a terminal and assign an IP on the same subnet:

    sudo ip addr add 169.254.1.1/24 dev enp0s31f6

Test the connection:

    ping 169.254.1.2

## Step 3: SSH in from laptop

    ssh pi@169.254.1.2

## Step 4: Fix autologin (if login screen shows)

Check if the session file exists:

    ls /usr/share/wayland-sessions/rpd-labwc.desktop

If it's missing, reinstall it (needs internet — connect RPi to wifi first
or share internet from laptop):

    sudo apt-get update && sudo apt-get install -y rpd-wayland-core

If no internet is available, create it manually:

    sudo tee /usr/share/wayland-sessions/rpd-labwc.desktop > /dev/null << 'EOF'
    [Desktop Entry]
    Name=RPi Desktop (labwc)
    Comment=Raspberry Pi Desktop on labwc
    Exec=/usr/bin/labwc
    Icon=labwc
    Type=Application
    DesktopNames=labwc;wlroots
    EOF

Verify autologin config:

    grep -v '^#\|^$' /etc/lightdm/lightdm.conf

Should contain under `[Seat:*]`:

    autologin-user=pi
    autologin-session=rpd-labwc

If not, fix it:

    sudo raspi-config nonint do_boot_behaviour B4

Then check the session name matches:

    ls /usr/share/wayland-sessions/

If `raspi-config` set `rpd-labwc` but only `labwc.desktop` exists, either
install `rpd-wayland-core` (preferred) or change the config:

    sudo sed -i 's/autologin-session=rpd-labwc/autologin-session=labwc/' /etc/lightdm/lightdm.conf

## Step 5: Fix double taskbar (if it happens)

If two taskbars appear at the top, remove the duplicate autostart:

    rm ~/.config/labwc/autostart

## Step 6: Reboot

    sudo reboot

Switch back to your laptop and wait for it to come back:

    ssh pi@169.254.1.2 'echo back'

## Step 7: Restore wifi

If you need to reconnect to wifi after recovery:

    ssh pi@169.254.1.2
    sudo nmcli device wifi connect "YourNetwork" password "YourPassword"

## Common causes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Login screen shows | `rpd-labwc.desktop` missing | Install `rpd-wayland-core` |
| Login screen shows | Wrong session name in lightdm config | Match session name to files in `/usr/share/wayland-sessions/` |
| Black screen + popup menu | Using bare `labwc` session without panel | Switch to `rpd-labwc` session |
| Double taskbar | `~/.config/labwc/autostart` launching extra panel | Delete the autostart file |
| Password rejected | Keyboard layout mismatch (QWERTZ) | Reset via SSH: `echo "pi:NewPass" \| sudo chpasswd` |
| RPi unreachable via cable | No IP on ethernet | Set manually: `sudo ip addr add 169.254.1.2/24 dev eth0` |
