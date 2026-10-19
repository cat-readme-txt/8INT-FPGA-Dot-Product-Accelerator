"""Check configuration startup and the physical board's active-low interface."""
import json
import os
from pathlib import Path
import cocotb
from cocotb.triggers import Timer


async def tick(dut, pressed=False):
    dut.clk.value = 0
    dut.btn_n.value = int(not pressed)
    await Timer(42, unit="ns")
    dut.clk.value = 1
    await Timer(42, unit="ns")
    dut.clk.value = 0


async def expect_pass(dut):
    for cycles in range(512):
        await tick(dut)
        if int(dut.led_green_n.value) == 0:
            assert int(dut.led_red_n.value) == 1
            return cycles+1
    assert False, "Board self-test never reached its pass indicator"


@cocotb.test()
async def startup_and_button_restart(dut):
    # Advance beyond startup before reading the status outputs.
    for _ in range(40):
        await tick(dut)
    first_cycles = await expect_pass(dut)
    for _ in range(20):
        await tick(dut)
        assert int(dut.led_green_n.value) == 0
        assert int(dut.led_red_n.value) == 1
    for _ in range(8):
        await tick(dut, pressed=True)
    assert int(dut.led_green_n.value) == 1
    assert int(dut.led_red_n.value) == 1
    restart_cycles = await expect_pass(dut)
    Path(os.environ["STATS_PATH"]).write_text(json.dumps({
        "core": os.environ["DUT_KIND"], "tests": [{
            "name": "startup_and_button_restart", "passed": True,
            "completed_selftests": 2, "vectors_per_run": 64,
            "cycles_after_startup_wait": first_cycles, "cycles_after_button_release": restart_cycles
        }]
    }, indent=2) + "\n")
