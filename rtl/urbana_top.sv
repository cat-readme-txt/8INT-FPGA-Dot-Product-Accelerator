`timescale 1ns/1ps
`default_nettype none

// Real Digital Urbana, XC7S50-CSGA324-1, 100 MHz oscillator.
// BTN0 and the discrete LEDs are active high.
module urbana_top #(
    parameter integer HEARTBEAT_BIT = 26
) (
    input  wire        clk_100mhz,
    input  wire        btn0,
    output wire [15:0] led
);
    // Configuration initializes these registers before the first clock edge.
    reg [4:0] startup = 5'h1f;
    (* ASYNC_REG = "TRUE" *) reg [1:0] button_sync = 2'b00;
    reg [26:0] heartbeat_count = 27'd0;

    always @(posedge clk_100mhz) begin
        button_sync <= {button_sync[0], btn0};
        heartbeat_count <= heartbeat_count + 27'd1;
        if (startup != 0)
            startup <= startup - 5'd1;
    end

    wire rst = (startup != 0) || button_sync[1];
    wire done, passed, failed;
    wire [6:0] checked_count;
    dot8_selftest selftest (
        .clk(clk_100mhz), .rst(rst), .done(done),
        .passed(passed), .failed(failed), .checked_count(checked_count)
    );

    // LED0: pass, LED1: mismatch, LED2: done, LED9: 64 checked.
    // LED15 blinks at about 0.75 Hz, showing that the board clock is live.
    assign led[0] = passed;
    assign led[1] = failed;
    assign led[2] = done;
    assign led[9:3] = checked_count;
    assign led[14:10] = 5'b0;
    assign led[15] = heartbeat_count[HEARTBEAT_BIT];
endmodule
`default_nettype wire
