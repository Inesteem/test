# Team 1: Buzzers

You own the physical buzzer input. Two deliverables: a server on the RPi that detects buzzer presses, and a client the game engine uses to read them.

## The Problem

3 identical USB buzzers are plugged into the RPi. Detect presses, track press order across all buzzers, and make that data available over the network.

## What You Know

- Vendor ID `0x2341`, Product ID `0xC036`
- They present as keyboard-like input devices
- The RPi is on the same network as the game laptop

## What You Need to Build

1. **RPi server** -- detect presses, track press order, serve over HTTP, support reset between questions. See `contracts.md`.

2. **Client** -- the game engine's interface to buzzer state. Must handle network errors gracefully (never crash).

## Things to Think About

- The 3 buzzers are identical -- how do you tell them apart?
- What happens to buffered events on reset?

## Stretch Goals

- A deploy script for the RPi
- Auto-discovery so the game master doesn't need to know the RPi's IP
