# Hardware Guide

This guide provides the list of required components and wiring instructions to build the physical part of the appliance.

## Recommended Components

*   **Raspberry Pi**: A Raspberry Pi 4 is recommended for best performance. A Pi Zero 2 W is also functional but will be significantly slower at processing.
*   **Microphone**: A USB microphone.
*   **Storage**: A high-quality microSD card (32GB or larger recommended).
*   **Power Supply**: An official Raspberry Pi power supply.
*   **Toggle Switch**: A standard SPST toggle switch.
*   **LED**: A standard 5mm LED (any color).
*   **Resistor**: A 330 Ohm resistor for the LED.
*   **Jumper Wires**: To connect the components.

## Wiring Instructions

Connect the components to the Raspberry Pi's GPIO header as follows:

1.  **Toggle Switch**: Connect one pin of the switch to **GPIO 23** (Pin 16) and the other pin to **GND** (Pin 14).
2.  **LED**: Connect the LED's longer lead (anode) to **GPIO 24** (Pin 18). Connect the shorter lead (cathode) to one end of the 330 Ohm resistor, and connect the other end of the resistor to **GND** (Pin 20).