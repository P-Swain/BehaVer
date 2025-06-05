module smart_traffic_light (
    input wire clk,
    input wire rst_n,
    input wire car_ns,        // Car present on North-South
    input wire car_ew,        // Car present on East-West
    input wire ped_button,    // Pedestrian crossing button
    output reg [1:0] light_ns, // 00=Red, 01=Green, 10=Yellow
    output reg [1:0] light_ew,
    output reg walk_signal     // 1 = allow pedestrian
);

    // State encoding
    typedef enum logic [2:0] {
        IDLE       = 3'b000,
        NS_GREEN   = 3'b001,
        NS_YELLOW  = 3'b010,
        EW_GREEN   = 3'b011,
        EW_YELLOW  = 3'b100,
        PED_CROSS  = 3'b101
    } state_t;

    state_t state, next_state;

    // Timer for delays
    integer timer;

    // State transition
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            timer <= 0;
        end else begin
            state <= next_state;

            // Decrease timer if running
            if (timer > 0)
                timer <= timer - 1;
        end
    end

    // Next state logic
    always @(*) begin
        next_state = state;  // default
        case (state)
            IDLE: begin
                if (car_ns)
                    next_state = NS_GREEN;
                else if (car_ew)
                    next_state = EW_GREEN;
            end
            NS_GREEN: begin
                if (timer == 0)
                    next_state = NS_YELLOW;
            end
            NS_YELLOW: begin
                if (timer == 0) begin
                    if (car_ew)
                        next_state = EW_GREEN;
                    else if (ped_button)
                        next_state = PED_CROSS;
                    else
                        next_state = IDLE;
                end
            end
            EW_GREEN: begin
                if (timer == 0)
                    next_state = EW_YELLOW;
            end
            EW_YELLOW: begin
                if (timer == 0) begin
                    if (car_ns)
                        next_state = NS_GREEN;
                    else if (ped_button)
                        next_state = PED_CROSS;
                    else
                        next_state = IDLE;
                end
            end
            PED_CROSS: begin
                if (timer == 0)
                    next_state = IDLE;
            end
        endcase
    end

    // Output and timer logic
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            light_ns <= 2'b00; // Red
            light_ew <= 2'b00;
            walk_signal <= 1'b0;
            timer <= 0;
        end else begin
            case (next_state)
                IDLE: begin
                    light_ns <= 2'b00; // Red
                    light_ew <= 2'b00;
                    walk_signal <= 0;
                end
                NS_GREEN: begin
                    light_ns <= 2'b01; // Green
                    light_ew <= 2'b00; // Red
                    walk_signal <= 0;
                    if (state != NS_GREEN)
                        timer <= 5;
                end
                NS_YELLOW: begin
                    light_ns <= 2'b10; // Yellow
                    light_ew <= 2'b00;
                    walk_signal <= 0;
                    if (state != NS_YELLOW)
                        timer <= 2;
                end
                EW_GREEN: begin
                    light_ns <= 2'b00;
                    light_ew <= 2'b01;
                    walk_signal <= 0;
                    if (state != EW_GREEN)
                        timer <= 5;
                end
                EW_YELLOW: begin
                    light_ns <= 2'b00;
                    light_ew <= 2'b10;
                    walk_signal <= 0;
                    if (state != EW_YELLOW)
                        timer <= 2;
                end
                PED_CROSS: begin
                    light_ns <= 2'b00;
                    light_ew <= 2'b00;
                    walk_signal <= 1;
                    if (state != PED_CROSS)
                        timer <= 4;
                end
            endcase
        end
    end

endmodule

