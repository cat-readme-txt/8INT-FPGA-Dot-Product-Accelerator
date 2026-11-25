# Urbana board build and bring-up

This guide builds the ROM self-test for the [Real Digital Urbana board](https://www.realdigital.org/hardware/urbana), then loads it through the board's USB/JTAG port. The target is the XC7S50-CSGA324-1 Spartan-7. The 100 MHz oscillator, BTN0, and 16 discrete LEDs use the board vendor's [reference constraints](https://www.realdigital.org/downloads/1f07b1146ec59e165634a5b6c782a17d.txt) and [reference manual](https://www.realdigital.org/doc/496fed57c6b275735fe24c85de5718c2). The iCEBreaker `.bin` file and `.pcf` constraints do not apply to Urbana.

The board runs all 64 deterministic dot-product vectors, compares the 19-bit results with independently generated expected values, and latches the result. The test covers the arithmetic pipeline, its input and output handshakes, and deliberate output stalls. The ROM is a demonstration workload; no UART host interface is present.

## Vivado in an Apple Silicon UTM VM

Vivado 2025.2 is an x86-64 Linux application. [UTM's Rosetta support](https://docs.getutm.app/advanced/rosetta/) can run x86-64 Linux programs inside an ARM64 guest that uses the Apple Virtualization backend. In that configuration, `uname -m` still prints `aarch64`; this alone does not rule out a working Vivado installation. This VM has already built the HackMidwest Urbana design using Rosetta, Bubblewrap, CPU-reporting shims, and a Java subprocess setting.

The stock `vivado` launcher may reject `aarch64` before the Tcl script runs. Use `make urbana-rosetta` below; it applies the compatibility steps from the working HackMidwest batch build. `make urbana` remains available for systems with a native or separately configured Vivado launcher.

## 1. Get the source into the Debian VM

The in-process Urbana Tcl build is already in commit `dc887d3`. The new Bubblewrap launcher and guide changes are currently local to the Mac checkout. After reviewing them, publish those changes so the VM can pull the launcher:

```bash
git add Makefile README.md URBANA_BRINGUP.md scripts/build_urbana_rosetta.sh
git commit -m "Add Rosetta launcher for Urbana Vivado build"
git push origin main
```

Then open a terminal in the existing Debian checkout:

```bash
cd ~/Projects/8INT-FPGA-Dot-Product-Accelerator
git pull --ff-only
git log -1 --oneline
```

Verify that `rtl/urbana_top.sv`, `constraints/urbana.xdc`, `scripts/build_urbana.tcl`, and `scripts/build_urbana_rosetta.sh` exist. The commit ID is useful when recording the test result.

Vivado must include the Spartan-7 device family. In this VM, Vivado 2025.2 is installed under `/home/qihan/amd/2025.2/Vivado`. The Rosetta target expects the existing executable shims at `~/vivado-compat/{uname,arch,lscpu}`, Bubblewrap (`bwrap`), and the working `vivado` command. Inspect them before building:

```bash
command -v bwrap vivado
ls -l ~/vivado-compat/{uname,arch,lscpu}
```

The target prepends `~/vivado-compat` to `PATH`, makes its `lscpu` replacement visible at `/usr/bin/lscpu` inside Bubblewrap, sets `JAVA_TOOL_OPTIONS` to select Java's `FORK` process launcher, and sets the locale to `C`. Rosetta and the VM's installed amd64 libraries still provide the execution environment. It does not change the VM architecture.

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

From the **Debian Bash prompt**, in the repository root, run:

```bash
make urbana-rosetta
```

If `vivado` is not on `PATH`, provide the executable that worked for HackMidwest: `VIVADO_BIN=/absolute/path/to/vivado make urbana-rosetta`. This target invokes Vivado with `-mode batch -source scripts/build_urbana.tcl` through Bubblewrap and writes its log and journal under `build/urbana`. Do not run `source scripts/build_urbana.tcl` at the Bash prompt: `source` would make Bash interpret Vivado Tcl commands. If using the Vivado GUI instead, enter `source /home/qihan/Projects/8INT-FPGA-Dot-Product-Accelerator/scripts/build_urbana.tcl` in **Vivado's Tcl Console** with no project open.

The script follows the same in-process, non-project flow as the proven [HackMidwest Rosetta build](https://github.com/Trade42/HackMidwest/blob/fpga/fpga_board/vivado/build_rosetta.tcl): it synthesizes part `xc7s50csga324-1`, places and routes `urbana_top` with `constraints/urbana.xdc`, writes reports, and creates `build/urbana/urbana_top.bit`. It does not program the board. The run should end with `Urbana bitstream ready:` and nonnegative setup and hold slack. It does not launch separate Vivado child runs or write a routed checkpoint.

The published Urbana constraint file and reference manual both assign the clock to N15. A [published prototype schematic](https://www.realdigital.org/downloads/064514e67fbab05a00650ce69af02486.pdf) labels the clock at P15 instead, so verify the revision of your board and use the heartbeat test below to confirm the clock pin on your hardware. Do not change the XDC pin by guesswork if the heartbeat stays dark.

Before transfer, inspect `build/urbana/timing_summary.rpt` for zero failing endpoints and zero unconstrained internal paths, `build/urbana/drc.rpt` for critical violations, and `build/urbana/io.rpt` for the expected N15 clock, J2 button, and LED pins. The batch script stops if it finds negative worst setup or hold slack; a successful file write alone is not a timing result. Save these reports with the build commit and Vivado version.

## 4. Transfer to the Mac and load volatile configuration

The working VM has a VirtioFS share at `/mnt/utm/UTMShared`, corresponding to `~/UTMShared` on the Mac. In Debian, after the build:

```bash
cp build/urbana/urbana_top.bit /mnt/utm/UTMShared/urbana_top.bit
sha256sum build/urbana/urbana_top.bit /mnt/utm/UTMShared/urbana_top.bit
```

The two hashes should match. On the Mac, run `shasum -a 256 ~/UTMShared/urbana_top.bit` to check the shared copy again. If the share is not mounted, use the UTM VirtioFS share setup from the working HackMidwest workflow or transfer the `.bit` by another method. Use the board's **main/programming micro-USB** port with a data-capable cable. Set power jumper J16 to `USB` if this cable supplies power. Leave programming jumper J14 **unloaded** for JTAG mode. The Mac owns the USB connection in this setup. The board's power indicators and green INIT indicator should be on before loading.

On the Mac, install [openFPGALoader](https://trabucayre.github.io/openFPGALoader/guide/first-steps.html) if needed. The working HackMidwest load on this Urbana used the `arty_s7_50` profile. Reuse that proven command for volatile configuration, changing only the bitstream filename:

```bash
brew install openfpgaloader
openFPGALoader -b arty_s7_50 ~/UTMShared/urbana_top.bit
```

That profile is a verified workaround for this particular Urbana programming setup, not an Urbana-specific board definition. If it fails to detect the board, inspect the USB interface and XC7S50 before retrying with explicit FT2232 channel A settings:

```bash
openFPGALoader --scan-usb
openFPGALoader -c ft2232 --ftdi-channel 0 --detect
openFPGALoader -c ft2232 --ftdi-channel 0 --fpga-part xc7s50csga324 ~/UTMShared/urbana_top.bit
```

These commands load FPGA configuration memory only. It is lost on power-off or when `PROG` is pressed. `--fpga-part` supplies the part for the direct-cable route. If detection fails, check the cable, J14/J16, and whether another program holds the FTDI interface.

The recorded macOS 26.6.2 Apple Virtualization VM did not have a working USB passthrough route for the board, so use the Mac for JTAG programming in this setup.

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

Only after the volatile load and restart test pass, use the board's QSPI configuration flash if persistent startup is desired. The board manual identifies a Micron `mt25ql128-spi-x1_x2_x4` configuration device and gives the [Vivado Hardware Manager sequence](https://www.realdigital.org/doc/496fed57c6b275735fe24c85de5718c2). That sequence needs access to the board's USB/JTAG interface; the current VM setup does not provide a proven passthrough route. Use a separately verified flash programmer setup before attempting this optional step. After programming and verifying the flash, move J14 to the loaded position and power-cycle; DONE and the same LED pass pattern should return without JTAG loading.

This step overwrites the current flash image. Preserve any existing image first if it matters. Do not treat a successful JTAG load as evidence that flash startup works; test the power-cycle separately. `openFPGALoader -f` is not the documented Urbana flash procedure, and this repository has no Urbana-specific flash profile.

## Completion record

The project has a physical-board result when the source revision is identified, simulation passes, Vivado implementation meets the 100 MHz constraint without critical DRC issues, the transferred bitstream is verified, and the Urbana shows the pass/count/heartbeat pattern and button restart. Persistent flash startup is an optional additional result. Report the actual Vivado slack and utilization, and keep the old iCE40 results separate from this Spartan-7 implementation.
