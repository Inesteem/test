# Team 1: Buzzers

You own the physical buzzer input pipeline. Two deliverables: a server that runs on the Raspberry Pi and reads buzzer presses, and a client library that the game engine imports.

## The Problem

The buzzers are USB devices that show up as Linux keyboard input devices. When someone presses a buzzer, it fires a keypress event. You need to:

1. Detect all connected buzzers
2. Listen for presses in the background
3. Track the order in which buzzers were pressed (the "ranking")
4. Serve this state over the network so the game laptop can read it
5. Support resetting the ranking between questions

## What You Know

- The buzzers have vendor ID `0x2341` and product ID `0xC036`
- They present as keyboard devices and send `KEY_K` on press
- The `evdev` Python library reads Linux input devices
- There may be two (or more) buzzers plugged in simultaneously -- they're identical devices, so you need stable enumeration (hint: the physical USB path helps)
- The RPi is on the same WiFi as the game laptop

## What You Need to Build

### On the RPi: HTTP Server

A lightweight HTTP server (stdlib `http.server` is fine) that exposes two endpoints:

- `GET /` -- returns the current buzzer state as JSON
- `POST /reset` -- clears the ranking for a new question

See `contracts.md` for the exact JSON shapes.

The server should start the buzzer listener in a background thread when it boots, and serve HTTP requests on the main thread.

### On the Laptop: Client Library

A `RemoteBuzzerController` class that Team 3 will import. It wraps HTTP calls to your server behind a clean Python interface.

See `contracts.md` for the exact class interface.

Key requirement: **never crash on network errors.** If the RPi is unreachable, return empty results. The game should degrade gracefully, not explode.

## Things to Think About

- Thread safety: the HTTP handler and the buzzer listener run concurrently
- Draining: when you reset, old buffered events should be discarded
- What happens if a buzzer is unplugged mid-game?
- The server should bind to `0.0.0.0` so it's reachable from the WiFi network

## Stretch Goals

- WebSocket or Server-Sent Events instead of polling
- Auto-discovery via mDNS (advertise `_buzzer._tcp.local`)
- A deploy script that copies code to the RPi and starts the server
