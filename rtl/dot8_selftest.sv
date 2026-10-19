`timescale 1ns/1ps
`default_nettype none

// Portable integration top: 64 ROM vectors, deliberate output stalls, sticky
// pass/fail status. The expected answers are generated independently in Python.
module dot8_selftest (
    input  wire        clk,
    input  wire        rst,
    output reg         done,
    output reg         passed,
    output reg         failed,
    output reg [6:0]   checked_count
);
    `include "selftest_rom.svh"
    reg [6:0] sent_count;
    reg [3:0] tick;
    wire in_valid = !rst && !done && (sent_count < 7'd64);
    wire in_ready;
    wire out_valid;
    wire out_ready = !rst && !done && (tick[2:0] != 3'd3);
    wire signed [18:0] out_data;
    wire [18:0] expected = rom_expected(checked_count[5:0]);

    dot8_pipeline core (
        .clk(clk), .rst(rst),
        .in_valid(in_valid), .in_ready(in_ready),
        .a_flat(rom_a(sent_count[5:0])),
        .b_flat(rom_b(sent_count[5:0])),
        .out_valid(out_valid), .out_ready(out_ready), .out_data(out_data)
    );

    always @(posedge clk) begin
        if (rst) begin
            sent_count <= 7'd0;
            checked_count <= 7'd0;
            tick <= 4'd0;
            done <= 1'b0;
            passed <= 1'b0;
            failed <= 1'b0;
        end else begin
            tick <= tick + 4'd1;
            if (in_valid && in_ready)
                sent_count <= sent_count + 7'd1;
            if (out_valid && out_ready) begin
                checked_count <= checked_count + 7'd1;
                if (out_data != expected)
                    failed <= 1'b1;
                if (checked_count == 7'd63) begin
                    done <= 1'b1;
                    passed <= !failed && (out_data == expected);
                end
            end
        end
    end
endmodule
`default_nettype wire
