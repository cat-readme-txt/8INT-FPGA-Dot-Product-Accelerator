`timescale 1ns/1ps
`default_nettype none

// Eight signed INT8 products, accumulated exactly into a signed 19-bit result.
// Lane i occupies a_flat[8*i +: 8] and b_flat[8*i +: 8].
// Four registered arithmetic stages. All stages freeze on output backpressure.
module dot8_pipeline (
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
    reg [3:0] valid_pipe;
    reg signed [15:0] product [0:7];
    reg signed [16:0] sum_pair [0:3];
    reg signed [17:0] sum_quad [0:1];
    reg signed [18:0] sum_octet;
    wire advance = !valid_pipe[3] || out_ready;

    assign in_ready = !rst && advance;
    assign out_valid = !rst && valid_pipe[3];
    assign out_data = sum_octet;

    // Reset clears validity; uninitialized datapath bits are never advertised.
    // Keeping reset off the arithmetic registers helps DSP register inference.
    always @(posedge clk) begin
        if (rst)
            valid_pipe <= 4'b0000;
        else if (advance)
            valid_pipe <= {valid_pipe[2:0], in_valid};
    end

    genvar lane;
    generate
        for (lane = 0; lane < 8; lane = lane + 1) begin : g_product
            wire signed [7:0] a_lane = a_flat[8*lane +: 8];
            wire signed [7:0] b_lane = b_flat[8*lane +: 8];
            always @(posedge clk)
                if (!rst && advance && in_valid)
                    product[lane] <= a_lane * b_lane;
        end
        for (lane = 0; lane < 4; lane = lane + 1) begin : g_pair
            always @(posedge clk)
                if (!rst && advance && valid_pipe[0])
                    sum_pair[lane] <=
                        $signed({product[2*lane][15], product[2*lane]}) +
                        $signed({product[2*lane+1][15], product[2*lane+1]});
        end
        for (lane = 0; lane < 2; lane = lane + 1) begin : g_quad
            always @(posedge clk)
                if (!rst && advance && valid_pipe[1])
                    sum_quad[lane] <=
                        $signed({sum_pair[2*lane][16], sum_pair[2*lane]}) +
                        $signed({sum_pair[2*lane+1][16], sum_pair[2*lane+1]});
        end
    endgenerate

    always @(posedge clk)
        if (!rst && advance && valid_pipe[2])
            sum_octet <= $signed({sum_quad[0][17], sum_quad[0]}) +
                         $signed({sum_quad[1][17], sum_quad[1]});
endmodule
`default_nettype wire
