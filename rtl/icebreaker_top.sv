`timescale 1ns/1ps
`default_nettype none

// iCEBreaker iCE40UP5K-SG48. Active-low user LEDs and user button.
module icebreaker_top (
    input  wire clk,
    input  wire btn_n,
    output wire led_green_n,
    output wire led_red_n
);
    // FPGA configuration initializes these registers. No derived clock.
    reg [4:0] startup = 5'h1f;
    (* ASYNC_REG = "TRUE" *) reg [1:0] button_sync = 2'b11;
    always @(posedge clk) begin
        button_sync <= {button_sync[0], btn_n};
        if (startup != 0)
            startup <= startup - 5'd1;
    end
    wire rst = (startup != 0) || !button_sync[1];
    wire done, passed, failed;
    wire [6:0] checked_count;
    dot8_selftest selftest (
        .clk(clk), .rst(rst), .done(done),
        .passed(passed), .failed(failed), .checked_count(checked_count)
    );
    assign led_green_n = !passed;
    assign led_red_n = !failed;
endmodule
`default_nettype wire
