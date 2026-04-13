# Team 1: Buzzers

You own the physical buzzer input. Two deliverables: a server on the Raspberry Pi that detects buzzer presses, and a client that the game engine uses to read them.

## The Problem

The buzzers are USB devices plugged into the RPi. When someone presses a buzzer, you need to detect it, track the press order across all buzzers, and make that data available to the game master laptop over the network.

## What You Know

- There are 3 buzzers, all identical USB devices
- Vendor ID `0x2341`, Product ID `0xC036`
- They present as keyboard-like input devices
- The RPi is on the same network as the game laptop

## What You Need to Build

1. **RPi server** -- detect buzzer presses, track press order ("ranking"), serve it over HTTP. Support resetting the ranking between questions. See `contracts.md` for the API.

2. **Laptop client** -- a clean interface the game engine imports to poll buzzer state. Must handle network errors gracefully (never crash, return safe defaults).

## Things to Think About

- Multiple buzzers are identical -- how do you tell them apart reliably?
- Thread safety between the input listener and HTTP handler
- What happens to buffered events when you reset?
- The server needs to be reachable from the network, not just localhost

## Stretch Goals

- A deploy script that copies code to the RPi and starts the server
- Auto-discovery so the game master doesn't need to know the RPi's IP
