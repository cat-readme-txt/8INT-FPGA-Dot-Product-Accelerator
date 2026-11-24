# Urbana board build and bring-up

This guide builds the ROM self-test for the [Real Digital Urbana board](https://www.realdigital.org/hardware/urbana), then loads it through the board's USB/JTAG port. The target is the XC7S50-CSGA324-1 Spartan-7. The 100 MHz oscillator, BTN0, and 16 discrete LEDs use the board vendor's [reference constraints](https://www.realdigital.org/downloads/1f07b1146ec59e165634a5b6c782a17d.txt) and [reference manual](https://www.realdigital.org/doc/496fed57c6b275735fe24c85de5718c2). The iCEBreaker `.bin` file and `.pcf` constraints do not apply to Urbana.

The board runs all 64 deterministic dot-product vectors, compares the 19-bit results with independently generated expected values, and latches the result. The test covers the arithmetic pipeline, its input and output handshakes, and deliberate output stalls. The ROM is a demonstration workload; no UART host interface is present.

## 1. Get the source into the Debian VM

The new Urbana files are local until committed and pushed. From this repository on the Mac, publish the reviewed changes so the VM can pull them:

```bash
git add Makefile README.md TECHNICAL_NOTES.md URBANA_BRINGUP.md \
    constraints/urbana.xdc rtl/urbana_top.sv \
    scripts/build_urbana.tcl scripts/run_tests.py tests/test_urbana.py
git commit -m "Add Urbana Spartan-7 board self-test"
git push origin main
```

Then open a terminal in the VM:

```bash
git clone https://github.com/cat-readme-txt/8INT-FPGA-Dot-Product-Accelerator.git
cd 8INT-FPGA-Dot-Product-Accelerator
git pull --ff-only
git log -1 --oneline
```

If the repository is already cloned, use `git pull --ff-only` from its directory. Verify that `rtl/urbana_top.sv`, `constraints/urbana.xdc`, and `scripts/build_urbana.tcl` exist. The commit ID is useful when recording the test result.

Vivado must include the Spartan-7 device family. `vivado -version` should work in the same terminal as the build. If it does not, source the Vivado installation's `settings64.sh` first, using its actual installation path, for example:

```bash
source /path/to/Vivado/2025.1/settings64.sh
vivado -version
```

## 2. Run simulation in Debian

Install the local simulation dependencies once:

```bash
sudo apt-get update
sudo apt-get install -y iverilog python3-venv make
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
make test
```

The expected result is 11 passing RTL tests, including `urbana_top` startup, clock indicator, button restart, and 64-vector completion. Simulation alone does not validate physical pins or routed timing.

## 3. Build the Urbana bitstream in Vivado

From the repository root, with Vivado on `PATH`:

```bash
make urbana
```

This runs `vivado -mode batch -source scripts/build_urbana.tcl`. It creates a Vivado project for part `xc7s50csga324-1`, implements the top `urbana_top` with `constraints/urbana.xdc`, writes reports, and copies the bitstream to `build/urbana/urbana_top.bit`. It does not program the board. The run should end with `Urbana bitstream ready:` and nonnegative setup and hold slack.

The published Urbana constraint file and reference manual both assign the clock to N15. A [published prototype schematic](https://www.realdigital.org/downloads/064514e67fbab05a00650ce69af02486.pdf) labels the clock at P15 instead, so verify the revision of your board and use the heartbeat test below to confirm the clock pin on your hardware. Do not change the XDC pin by guesswork if the heartbeat stays dark.

Before transfer, inspect `build/urbana/timing_summary.rpt` for zero failing endpoints and zero unconstrained internal paths, `build/urbana/drc.rpt` for critical violations, and `build/urbana/io.rpt` for the expected N15 clock, J2 button, and LED pins. The batch script stops if it finds negative worst setup or hold slack; a successful file write alone is not a timing result. Save these reports with the build commit and Vivado version.

## 4. Transfer to the Mac and load volatile configuration

Transfer `build/urbana/urbana_top.bit` to the Mac through a UTM shared directory, `scp`, or another file transfer. For example, if SSH is enabled in Debian and reachable from the Mac:

```bash
scp user@vm-host:/path/to/repo/build/urbana/urbana_top.bit ~/Downloads/
shasum -a 256 ~/Downloads/urbana_top.bit
```

Run `sha256sum build/urbana/urbana_top.bit` in Debian and compare the result. Use the board's **main/programming micro-USB** port with a data-capable cable. Set power jumper J16 to `USB` if this cable supplies power. Leave programming jumper J14 **unloaded** for JTAG mode. The Mac must own the USB device; disconnect it from UTM USB passthrough if the VM captured it. The board's power indicators and green INIT indicator should be on before loading.

On the Mac, install [openFPGALoader](https://trabucayre.github.io/openFPGALoader/guide/first-steps.html) if needed, then detect the FPGA before attempting to load:

```bash
brew install openfpgaloader
openFPGALoader --scan-usb
openFPGALoader -c ft2232 --ftdi-channel 0 --detect
```

The Urbana has an FT2232H USB interface with JTAG on channel A. `openFPGALoader` does not list an `urbana` board profile, so use the cable directly. Confirm that detection reports the XC7S50 before running:

```bash
openFPGALoader -c ft2232 --ftdi-channel 0 --fpga-part xc7s50csga324 ~/Downloads/urbana_top.bit
```

This loads FPGA configuration memory only. It is lost on power-off or when `PROG` is pressed. `--fpga-part` supplies the part for this board without a built-in loader profile. If detection fails, check the cable, J14/J16, UTM USB ownership, and whether another program holds the FTDI interface. Do not use another board's `-b` profile solely because it has the same FPGA package.

If openFPGALoader cannot detect the FTDI/JTAG interface, attach the Urbana USB device to the Debian VM through UTM, open Vivado Hardware Manager, choose **Open Target → Autoconnect**, and use **Program Device** with `build/urbana/urbana_top.bit`. The board manual documents this path. Disconnect the USB device from the Mac's loader before handing it to the VM.

## 5. Read the board result

The board's green **DONE** configuration LED should light after programming. It is separate from the 16 user LEDs and only reports successful configuration. The user LEDs report the design's self-test:

| Indicator | Expected after a pass | Meaning |
| --- | --- | --- |
| LED0 | On | All 64 results matched |
| LED1 | Off | No arithmetic mismatch |
| LED2 | On | Test completed |
| LED9 | On | Count reached 64 (`checked_count[6]`) |
| LED3–LED8 | Off | Lower count bits are zero at 64 |
| LED15 | Blinking | The 100 MHz board clock is running |

Hold BTN0: LED0, LED2, and LED9 should turn off. Release it: the self-test should finish and those LEDs should return on. The 64-vector run completes in microseconds, so the intermediate count is too fast to see by eye. The heartbeat continues while the button is held. The status LEDs are active high; BTN0 is active high.

Record a short video or photos of the pass state and button restart, plus the command output, SHA-256, Vivado reports, board revision, and git commit. If LED15 blinks but LED0 never lights, check LED1 for a mismatch and inspect the simulation and timing reports. If DONE is off, diagnose programming before interpreting user LEDs.

## 6. Optional persistent flash configuration

Only after the volatile load and restart test pass, use the board's QSPI configuration flash if persistent startup is desired. Attach the board's USB device to the Debian VM through UTM for this Vivado step. The board manual identifies a Micron `mt25ql128-spi-x1_x2_x4` configuration device. In Vivado Hardware Manager, add that configuration memory device, generate an MCS file from the **same tested** `.bit` at address 0, and program and verify the device. The [Urbana reference manual](https://www.realdigital.org/doc/496fed57c6b275735fe24c85de5718c2) gives the GUI sequence. Move J14 to the loaded position and power-cycle; DONE should light and the same LED pass pattern should return without JTAG loading.

This step overwrites the current flash image. Preserve any existing image first if it matters. Do not treat a successful JTAG load as evidence that flash startup works; test the power-cycle separately. `openFPGALoader -f` is not the documented Urbana flash procedure, and this repository has no Urbana-specific flash profile.

## Completion record

The project has a physical-board result when the source revision is identified, simulation passes, Vivado implementation meets the 100 MHz constraint without critical DRC issues, the transferred bitstream is verified, and the Urbana shows the pass/count/heartbeat pattern and button restart. Persistent flash startup is an optional additional result. Report the actual Vivado slack and utilization, and keep the old iCE40 results separate from this Spartan-7 implementation.
