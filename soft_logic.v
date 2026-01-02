// For soft reg

// Basic ML block
//(* keep_hierarchy *)
module ml_block #(
    parameter ADDR_WIDTH = 3,
    parameter DATA_WIDTH = 8
)
(
   input clk,
   input [31:0] a,
   input [23:0] b,
   input [23:0] b_cas_in,
   input [127:0] res_cas_in,
   input a_en,
   input b_en,
   input acc_en,
   input config_en,
   input hp_en,
   input config_in,
   input reset,

   output reg [31:0] a_out,
   output reg [23:0] b_out,
   output reg [23:0] b_cas_out,
   output reg [127:0] res_cas_out,
   output reg [127:0] res_out,
   output reg config_out


//   input  clk ,
//   input  load_weight_en ,
//   input  input_data_en ,
//   input  acc_en,
//   input  [DATA_WIDTH-1:0] weight_in ,
//   input  [DATA_WIDTH-1:0] data_in ,
//   input  [DATA_WIDTH*2-1:0] full_data_in ,
//   output  reg  [DATA_WIDTH-1:0] data_out ,
//   output reg  [DATA_WIDTH-1:0] weight_out ,
//   output reg  [DATA_WIDTH*2-1:0] full_data_out ,
  
//   input  reset 
);


  // Internal computation signals
   //  reg  [31:0]      a_reg;
   //  reg  [23:0]      b_reg;
   //  reg signed [127:0] acc_reg;
   //  wire signed [127:0] relu_result;

   //  assign relu_result = (acc_reg < 0) ? 128'd0 : acc_reg;

   //  // Internal RAM write enables
   //  reg  [5:0] addr_counter;

   //  wire [31:0]  a_out_ram;
   //  wire [23:0]  b_out_ram;
   //  wire [23:0]  b_cas_out_ram;
   //  wire [127:0] res_cas_out_ram;
   //  wire [127:0] res_out_ram;
   //  wire         config_out_ram;

   //  // Assign to outputs
   //  assign a_out        = a_out_ram;
   //  assign b_out        = b_out_ram;
   //  assign b_cas_out    = b_cas_out_ram;
   //  assign res_cas_out  = res_cas_out_ram;
   //  assign res_out      = res_out_ram;
   //  assign config_out   = config_out_ram;

   //  // RAM instantiations
   //  single_port_ram #(.ADDR_WIDTH(6), .DATA_WIDTH(32)) a_out_mem (
   //      .clk(clk), .addr(addr_counter), .data(a_reg), .we(a_en), .out(a_out_ram)
   //  );

   //  single_port_ram #(.ADDR_WIDTH(6), .DATA_WIDTH(24)) b_out_mem (
   //      .clk(clk), .addr(addr_counter), .data(b_reg), .we(b_en), .out(b_out_ram)
   //  );

   //  single_port_ram #(.ADDR_WIDTH(6), .DATA_WIDTH(24)) b_cas_out_mem (
   //      .clk(clk), .addr(addr_counter), .data(b_cas_in), .we(b_en), .out(b_cas_out_ram)
   //  );

   //  single_port_ram #(.ADDR_WIDTH(6), .DATA_WIDTH(128)) res_cas_out_mem (
   //      .clk(clk), .addr(addr_counter), .data(res_cas_in), .we(acc_en), .out(res_cas_out_ram)
   //  );

   //  single_port_ram #(.ADDR_WIDTH(6), .DATA_WIDTH(128)) res_out_mem (
   //      .clk(clk), .addr(addr_counter), .data(relu_result), .we(acc_en), .out(res_out_ram)
   //  );

   //  single_port_ram #(.ADDR_WIDTH(6), .DATA_WIDTH(1)) config_out_mem (
   //      .clk(clk), .addr(addr_counter), .data(config_in), .we(config_en), .out(config_out_ram)
   //  );

   //  // Counter for addressing (can be replaced by external control)
   //  always @(posedge clk or posedge reset) begin
   //      if (reset) begin
   //          addr_counter <= 6'd0;
   //          a_reg        <= 32'd0;
   //          b_reg        <= 24'd0;
   //          acc_reg      <= 128'd0;
   //      end else begin
   //          addr_counter <= addr_counter + 1;

   //          if (a_en)
   //              a_reg <= a;

   //          if (b_en)
   //              b_reg <= b;

   //          if (acc_en) begin
   //              acc_reg <= $signed(res_cas_in) + ($signed(a_reg[23:0]) * $signed(b_reg));
   //          end
   //      end
   //  end


   // // Internal registers
    reg [31:0]  a_reg;
    reg [23:0]  b_reg;
    reg [127:0] accumulator;


// single_port_ram #(   .ADDR_WIDTH(6), 
//             .DATA_WIDTH(32)) 
    
//     mem(    .clk(clk),
//             .addr(addr),
//             .data(weight_in),
//             .we(load_weight_en),
//             .out(weight_out)
// );

    always @(posedge clk or posedge reset) begin
        if (reset) begin
            a_reg       <= 32'd0;
            b_reg       <= 24'd0;
            accumulator <= 128'd0;

            a_out       <= 32'd0;
            b_out       <= 24'd0;
            b_cas_out   <= 24'd0;
            res_cas_out <= 128'd0;
            res_out     <= 128'd0;
            config_out  <= 1'b0;

        end else begin
            // Capture inputs if enabled
            if (1) begin
                a_reg  <= a;
                a_out  <= a;
            end

            if (1) begin
                b_reg    <= b;
                b_out    <= b;
                
            end begin
                b_cas_out <= b_cas_in;
            end

            // Configuration propagation (mock logic)
            if (1) begin
                config_out <= config_in;
            end

            // Perform multiply-accumulate if enabled
            if (1) begin
                // Example: lower-precision multiply (truncate for now)
                // In real designs, handle fixed-point or floating-point carefully
                reg [55:0] mac_result;  // 32 x 24 = 768 bits max → simplified
                mac_result = a_reg * b_reg;  // simulate lower precision

                accumulator <= res_cas_in + mac_result;
                res_out     <= accumulator;
                res_cas_out <= accumulator;
            end
        end
    end




// reg [DATA_WIDTH-1:0] weight;
// reg [DATA_WIDTH-1:0] data;
// reg [DATA_WIDTH*2-1:0] data_to_relu;
// reg [ADDR_WIDTH-1:0] addr;

// single_port_ram #(   .ADDR_WIDTH(ADDR_WIDTH), 
//             .DATA_WIDTH(DATA_WIDTH)) 
    
//     mem(    .clk(clk),
//             .addr(addr),
//             .data(weight_in),
//             .we(load_weight_en),
//             .out(weight_out)
// );

// always@(posedge clk)begin
//    if (reset) begin
//       addr <= 0;
//    end
//    else begin
//       addr <= addr + 1;
//    end
// end
//    always @ (*) begin
//       if (reset) begin
//          data_out = 0;     
//         end
//       else begin
//          // if (load_weight_en) begin
//          //    weight <= weight_in;
//          // end
//          // Latch
//          data_out = weight_in*data_in;       
//       end
//    end

// // Basic activation on accumulation (ReLU) with acc enable
// // ReLU
//    assign full_data_out = (data_out[DATA_WIDTH-1] & 1) ? 0 : data_out;       
   // assign data_out = data;








endmodule

//(* keep_hierarchy *)
module ml_block_weights #(
    parameter ADDR_WIDTH = 2,
    parameter DATA_WIDTH = 128
)
(
//   input  clk ,
  input  clk_portain ,
  input  clk_portaout ,
  input  clr0 ,
  input  clr1 ,
  input  ena0 ,
  input  ena1 ,
  input  ena2 ,
  input  ena3 ,
  input [ADDR_WIDTH-1:0] portaaddr ,
  input  portaaddrstall ,
  input  portabyteenamasks ,
  input [DATA_WIDTH-1:0] portadatain ,
  output reg [DATA_WIDTH-1:0] portadataout ,
  input  portare ,
  input  portawe 
//   input  reset 
);
   // reg [127:0] 	Mem [0:(1<<2)-1];
   // always @ (*) begin
   //    portadataout = Mem[portaaddr];
   // end
   // always @ (posedge clk) begin
   //      if (reset) begin
   //                for (integer i=0; i < 1<<ADDR_WIDTH; i++)
	//         Mem[i] <= 0;
   //      end
   //    if (portawe) begin
   //       Mem[portaaddr] <= portadatain;	 
   //    end
   // end

single_port_ram #(   .ADDR_WIDTH(ADDR_WIDTH), 
            .DATA_WIDTH(DATA_WIDTH)) 
    
    mem(    .clk(clk_portain),
            .addr(portaaddr),
            .data(portadatain),
            .we(portawe),
            .out(portadataout)
);


endmodule

//(* keep_hierarchy *)
module ml_block_input #(
    parameter ADDR_WIDTH = 8,
    parameter DATA_WIDTH = 32
		    )
(
//   input  clk ,
  input  clk_portain ,
  input  clk_portaout ,
  input  clr0 ,
  input  clr1 ,
  input  ena0 ,
  input  ena1 ,
  input  ena2 ,
  input  ena3 ,
  input [ADDR_WIDTH-1:0] portaaddr ,
  input  portaaddrstall ,
  input  portabyteenamasks ,
  input [DATA_WIDTH-1:0] portadatain ,
  output reg [DATA_WIDTH-1:0] portadataout ,
  input  portare ,
  input  portawe 
//   input  reset 
);
   // reg [DATA_WIDTH-1:0] 	Mem [0:(1<<ADDR_WIDTH)-1];
    
   // always @ (*) begin
   //    portadataout = Mem[portaaddr];
   // end
   // always @ (posedge clk) begin
   //      if (reset) begin
   //          for (integer i=0; i < 1<<ADDR_WIDTH; i++)
	//             Mem[i] <= 0;
   //      end
   //    if (portawe) begin
   //       Mem[portaaddr] <= portadatain;	 
   //    end
   // end

   single_port_ram #(   .ADDR_WIDTH(ADDR_WIDTH), 
            .DATA_WIDTH(DATA_WIDTH)) 
    
    mem(    .clk(clk_portain),
            .addr(portaaddr),
            .data(portadatain),
            .we(portawe),
            .out(portadataout)
);
// assign portadataout = portadatain;
endmodule

//(* keep_hierarchy *)
module emif_inner #(
    parameter ADDR_WIDTH = 12,
    parameter DATA_WIDTH = 128
		    )
(
  input  clk ,
  input [ADDR_WIDTH-1:0] address ,
  
  input [DATA_WIDTH-1:0] datain ,
  output reg [DATA_WIDTH-1:0] dataout ,
  input  reset ,
  input  wen 
);
   // reg [DATA_WIDTH-1:0] 	data [0:(1<<ADDR_WIDTH)-1];

   // always @ (*) begin
   //    dataout = data[address];
   // end
   // always @ (posedge clk) begin
   //    if (reset) begin
   //      for (integer i=0; i < 1<<ADDR_WIDTH; i++)
	//         data[i] <= 0;
   //    end
   //    if (wen) begin
   //       data[address] <= datain;	 
   //    end
   // end
   reg [DATA_WIDTH-1:0] data_temp;

   always @(posedge clk) begin
      if (reset)
         dataout <= 'h0;
      else begin
         dataout <= data_temp;
      end
   end
   single_port_ram #(   .ADDR_WIDTH(ADDR_WIDTH), 
            .DATA_WIDTH(DATA_WIDTH)) 
    
    mem(    .clk(clk),
            .addr(address),
            .data(datain),
            .we(wen),
            .out(data_temp)
);
// assign dataout = datain;
endmodule

//(* keep_hierarchy *)
module emif #(
    parameter ADDR_WIDTH = 12,
    parameter DATA_WIDTH = 128
		    )
(
  input  clk ,
  input [ADDR_WIDTH-1:0] address ,
  
  input read,
  
  input [DATA_WIDTH-1:0] writedata ,
  output reg [DATA_WIDTH-1:0] readdata ,
  input  reset ,
  output reg waitrequest,
  output reg readdatavalid,
  input  write
);
   // reg [DATA_WIDTH-1:0] 	data [0:(1<<ADDR_WIDTH)-1];

   // assign readdatavalid = 1;
   
   // always @ (*) begin
   //    if (read)
   //       readdata = data[address];
   // end
   // always @ (posedge clk) begin
   //    if (reset) begin
   //      for (integer i=0; i < 1<<ADDR_WIDTH; i++)
	//         data[i] <= 0;
   //    end
   //    if (write) begin
   //       data[address] <= writedata;	 
   //    end
   // end

   reg [DATA_WIDTH-1:0] data_temp;

   always @(posedge clk) begin
      if (reset)
         readdata <= 'h0;
      else begin
         readdata <= data_temp;
      end
   end

   single_port_ram #(   .ADDR_WIDTH(ADDR_WIDTH), 
            .DATA_WIDTH(DATA_WIDTH)) 
    
    mem(    .clk(clk),
            .addr(address),
            .data(writedata),
            .we(write),
            .out(data_temp)
);

   // assign readdata = writedata;
endmodule
