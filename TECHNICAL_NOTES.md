# Technical notes

These notes explain the design and verification of the
[INT8 dot-product accelerator](README.md). Numerical results and tool versions
are recorded in the [validation evidence](evidence/VALIDATION.md) and
[tool-version record](evidence/tool_versions.json).

## Arithmetic widths

The design computes an exact integer dot product. It has no requantization or
activation function. A neural-network layer would add its own scale handling.

| Stage | Width | Reason |
| --- | --- | --- |
| Signed product | 16 bits | Exact multiplication of two signed 8-bit values |
| Pair sum | 17 bits | Two products can sum to 32768 |
| Quad sum | 18 bits | Four products can sum to 65536 |
| Final sum | 19 bits | Eight products can sum to 131072 |

The last value is one greater than the maximum signed 18-bit integer. Each
adder explicitly sign-extends its operands before evaluation. Truncating an
intermediate expression can fail only at particular operand extremes, which
is why the directed tests include all lanes set to -128.

## Pipelining and latency

The parallel design registers the multiplier outputs. Its reduction tree has
a register after each level. Each arithmetic stage handles a different vector
once the pipeline fills. One result per cycle describes throughput; it does
not mean an individual vector traverses all stages in one cycle.

The testbench measures input acceptance and output retirement at rising edges.
With no stalls, retirement occurs four edges after acceptance.

## Backpressure

The global `advance` signal is true when the last stage is empty or the receiver
is ready. When a valid output is blocked, all arithmetic registers freeze.
Their associated valid bits freeze with them, preserving transaction alignment.

This is a deliberately simple implementation. An individually elastic pipeline
could absorb bubbles in earlier stages while the last stage is blocked. That
would require a ready condition for each stage rather than one global enable.

## Serial baseline

The serial version captures the input vectors, then accumulates one lane per
cycle with a shared multiplier. Its explicit load cycle makes its initiation
interval nine cycles. A more aggressive serial architecture could overlap
loading with the final accumulation; this baseline does not implement that
optimization.

Its wide operand storage and lane-selection multiplexers consume LUTs and
flip-flops. Saving DSP blocks does not imply that every other resource count
must fall. The [Artix-7 synthesis summary](evidence/artix7_summary.json)
reports the mapped cell counts.

## Verification

The Python scoreboard records an expected result only after an input handshake.
It compares only retired output transactions. This separates computation from
interface timing without assuming a fixed latency during stalls.

The testbench also checks output stability under backpressure. Reset explicitly
flushes the scoreboard, followed by an idle period that detects stale outputs.
The no-stall test independently checks every initiation interval and latency.

Random input data alone would not sufficiently exercise the interface. The
suite adds prolonged output stalls and input bubbles to stress flow control.

## FPGA mapping and timing

The Artix-7 resource comparison applies to standalone arithmetic cores. The
iCE40 timing report applies to the complete ROM self-test application. Resource
numbers from different FPGA families should not be compared as equivalent area.

The iCE40 build targets its physical board oscillator at 12 MHz. The reported
maximum frequency is a static estimate from the routed design. It is not a
measurement from a physical board and does not mean the board is clocked at
that maximum frequency.

The two-register button synchronizer handles the asynchronous user input.
It does not implement button debouncing. Holding reset through contact bounce
restarts the short self-test; the core remains in one clock domain.

## Result scope and reproducibility

The retained validation run reports ten RTL tests and one mapped-netlist test
passing, with 13,846 exact output matches per arithmetic core. The latter test
is a functional simulation using iCE40 primitive models; it has no SDF delay
annotation. No connected-board test is recorded for the included bitstream or
the current source.

The [source hashes](evidence/source_hashes.json) identify the files used for
the retained reports. The prebuilt bitstream is not covered by that hash list.
Different tool versions can change placement, resource counts, timing, and
bitstream bytes. A physical board run and a routed Artix-7 timing result remain
outside the validation scope.
