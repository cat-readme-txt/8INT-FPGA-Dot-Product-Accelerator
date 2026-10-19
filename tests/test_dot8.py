"""Bit-exact arithmetic plus streaming protocol verification against real RTL."""
from collections import deque
import json
import os
from pathlib import Path
import random

import cocotb
from cocotb.triggers import Timer

KIND = os.environ["DUT_KIND"]
RESULTS = {"core": KIND, "tests": []}


def pack(values):
    assert len(values) == 8
    return sum((value & 255) << (8 * i) for i, value in enumerate(values))


def random_vector(rng):
    return [rng.randrange(-128, 128) for _ in range(8)]


class Monitor:
    def __init__(self, dut):
        self.dut = dut
        self.expected = deque()
        self.previous_stall = None
        self.cycles = 0
        self.accepted = 0
        self.retired = 0
        self.flushed = 0
        self.output_stall_cycles = 0
        self.input_blocked_cycles = 0
        self.accept_cycles = []
        self.latencies = []
        dut.clk.value = 0

    async def cycle(self, a=None, b=None, valid=False, ready=True, rst=False):
        d = self.dut
        d.clk.value = 0
        d.rst.value = int(rst)
        d.in_valid.value = int(valid)
        d.out_ready.value = int(ready)
        d.a_flat.value = pack(a) if a is not None else 0
        d.b_flat.value = pack(b) if b is not None else 0
        await Timer(5, unit="ns")
        self.cycles += 1
        input_ready = int(d.in_ready.value)
        output_valid = int(d.out_valid.value)
        if rst:
            assert not input_ready and not output_valid, "Reset must suppress both handshakes"
            self.flushed += len(self.expected)
            self.expected.clear()
            self.previous_stall = None
        else:
            if self.previous_stall is not None:
                assert output_valid, "Output valid was withdrawn under backpressure"
                assert int(d.out_data.value) == self.previous_stall, "Stalled output changed"
            if valid and input_ready:
                self.expected.append((sum(x*y for x, y in zip(a, b)), self.cycles))
                self.accepted += 1
                self.accept_cycles.append(self.cycles)
            if output_valid:
                raw = int(d.out_data.value)
                if ready:
                    assert self.expected, "Unexpected or duplicated output transaction"
                    expected, accepted_cycle = self.expected.popleft()
                    actual = raw - (1 << 19) if raw & (1 << 18) else raw
                    assert actual == expected, f"Expected {expected}; received {actual}"
                    self.latencies.append(self.cycles - accepted_cycle)
                    self.retired += 1
            self.previous_stall = int(d.out_data.value) if output_valid and not ready else None
            self.output_stall_cycles += int(output_valid and not ready)
            self.input_blocked_cycles += int(valid and not input_ready)
        d.clk.value = 1
        await Timer(5, unit="ns")
        d.clk.value = 0
        return bool(valid and input_ready and not rst)

    async def reset(self):
        for _ in range(3):
            await self.cycle(rst=True)

    async def drain(self):
        for _ in range(64):
            await self.cycle()
            if not self.expected:
                break
        assert not self.expected, "Transactions failed to drain"
        for _ in range(12):
            await self.cycle()
        assert self.accepted == self.retired + self.flushed

    def save(self, name, **extra):
        result = {
            "name": name, "passed": True, "cycles": self.cycles,
            "accepted": self.accepted, "retired": self.retired, "reset_flushed": self.flushed,
            "output_stall_cycles": self.output_stall_cycles,
            "input_blocked_cycles": self.input_blocked_cycles,
        }
        result.update(extra)
        RESULTS["tests"].append(result)
        Path(os.environ["STATS_PATH"]).write_text(json.dumps(RESULTS, indent=2) + "\n")


async def send_vectors(monitor, vectors, rng=None):
    index = 0
    pending = None
    budget = len(vectors) * 80 + 200
    for local_cycle in range(budget):
        if pending is None and index < len(vectors) and (rng is None or rng.random() < 0.8):
            pending = vectors[index]
        # Long deterministic stalls supplement the random ready pattern.
        ready = True if rng is None else rng.random() < 0.68 and local_cycle % 257 >= 31
        accepted = await monitor.cycle(*(pending or (None, None)), valid=pending is not None, ready=ready)
        if accepted:
            index += 1
            pending = None
        if index == len(vectors):
            break
    assert index == len(vectors), "Input transfer timed out"
    await monitor.drain()


@cocotb.test()
async def directed_signed_arithmetic(dut):
    m = Monitor(dut)
    await m.reset()
    cases = [([0]*8, [0]*8), ([-128]*8, [-128]*8), ([127]*8, [127]*8),
             ([-128]*8, [127]*8), ([127]*8, [-128]*8),
             ([127, -128]*4, [-128, 127]*4)]
    for lane in range(8):
        a = [0]*8
        b = [0]*8
        a[lane] = -128
        b[lane] = -128
        cases.append((a.copy(), b.copy()))
        b[lane] = 127
        cases.append((a.copy(), b.copy()))
    await send_vectors(m, cases)
    m.save("directed_signed_arithmetic", vector_count=len(cases))


@cocotb.test()
async def randomized_backpressure(dut):
    m = Monitor(dut)
    await m.reset()
    seeds = [42, 2026, 8675309]
    for seed in seeds:
        rng = random.Random(seed)
        vectors = [(random_vector(rng), random_vector(rng)) for _ in range(4096)]
        await send_vectors(m, vectors, rng)
    assert m.output_stall_cycles > 100
    assert m.input_blocked_cycles > 100
    m.save("randomized_backpressure", seeds=seeds, vector_count=3*4096)


@cocotb.test()
async def reset_discards_inflight_transactions(dut):
    m = Monitor(dut)
    await m.reset()
    rng = random.Random(1107)
    for wait_for_output in [False, True]:
        a, b = random_vector(rng), random_vector(rng)
        while not await m.cycle(a, b, valid=True, ready=False):
            pass
        if wait_for_output:
            for _ in range(20):
                await m.cycle(ready=False)
            assert int(dut.out_valid.value) == 1
        else:
            await m.cycle(ready=False)
        assert m.expected
        await m.reset()
        for _ in range(12):
            await m.cycle()
        vectors = [(random_vector(rng), random_vector(rng)) for _ in range(256)]
        await send_vectors(m, vectors, rng)
    assert m.flushed == 2
    m.save("reset_discards_inflight_transactions")


@cocotb.test()
async def sustained_throughput_and_latency(dut):
    m = Monitor(dut)
    await m.reset()
    rng = random.Random(1949)
    vectors = [(random_vector(rng), random_vector(rng)) for _ in range(1024)]
    await send_vectors(m, vectors)
    expected_ii = 1 if KIND == "pipeline" else 9
    expected_latency = 4 if KIND == "pipeline" else 9
    gaps = [b-a for a, b in zip(m.accept_cycles, m.accept_cycles[1:])]
    assert set(gaps) == {expected_ii}, f"Unexpected initiation intervals: {set(gaps)}"
    assert set(m.latencies) == {expected_latency}, f"Unexpected latencies: {set(m.latencies)}"
    m.save("sustained_throughput_and_latency", vector_count=1024,
           initiation_interval_cycles=expected_ii, transfer_latency_cycles=expected_latency,
           sustained_results_per_cycle=1/expected_ii)
