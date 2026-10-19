`timescale 1ns/1ps
`default_nettype none

// Resource-sharing baseline: one signed multiplier, eight accumulation cycles.
// An additional input-load cycle gives a no-stall initiation interval of 9.
module dot8_serial (
    input  wire               clk,
    input  wire               rst,
    input  wire               in_valid,
    output wire               in_ready,
    input  wire [63:0]        a_flat,
    input  wire [63:0]        b_flat,
    output wire               out_valid,
    input  wire               out_ready,
    output wire signed [18:0] out_data
);
    reg busy;
    reg valid_reg;
    reg [63:0] a_reg, b_reg;
    reg [2:0] index;
    reg signed [18:0] accumulator;
    reg signed [18:0] result_reg;
    wire signed [7:0] a_lane = a_reg[8*index +: 8];
    wire signed [7:0] b_lane = b_reg[8*index +: 8];
    wire signed [15:0] product = a_lane * b_lane;
    wire signed [18:0] extended_product = {{3{product[15]}}, product};

    assign in_ready = !rst && !busy && (!valid_reg || out_ready);
    assign out_valid = !rst && valid_reg;
    assign out_data = result_reg;

    always @(posedge clk) begin
        if (rst) begin
            busy <= 1'b0;
            valid_reg <= 1'b0;
            index <= 3'd0;
            accumulator <= 19'sd0;
        end else begin
            if (valid_reg && out_ready)
                valid_reg <= 1'b0;
            if (in_valid && in_ready) begin
                a_reg <= a_flat;
                b_reg <= b_flat;
                accumulator <= 19'sd0;
                index <= 3'd0;
                busy <= 1'b1;
            end else if (busy) begin
                if (index == 3'd7) begin
                    result_reg <= accumulator + extended_product;
                    valid_reg <= 1'b1;
                    busy <= 1'b0;
                end else begin
                    accumulator <= accumulator + extended_product;
                    index <= index + 3'd1;
                end
            end
        end
    end
endmodule
`default_nettype wire
