//main.cpp
#include <cstdint>
#include <iostream>
#include <iomanip>
#include "scrutiny.hpp"

uint32_t get_timestamp_microsec();

uint8_t scrutiny_rx_buffer[64];
uint8_t scrutiny_tx_buffer[128];

// the function below can be invoked remotely by a Scrutiny client through the Python SDK
void my_user_command_callback(
    uint8_t const subfunction,          // ID coming from the SDK
    uint8_t const *request_data,        // Input data coming from the SDK
    uint16_t const request_data_length, // Length of input data
    uint8_t *response_data,             // Output data to send back to the SDK
    uint16_t *response_data_length,     // Length of output data
    uint16_t const response_max_data_length // Maximum size of the output buffer. Dictated by the TX Buffer size.
)
{
    if (subfunction == 1){
        std::cout << "Hello" << std::endl;
    } 
    else if (subfunction == 2) {
        std::cout << " World" << std::endl;
    }
    else if (subfunction == 3) {
        std::cout << "Received: ";
        for (uint32_t i=0; i<request_data_length; i++){
            std::cout << std::hex << static_cast<uint32_t>(request_data[i]);
        }
        std::cout << std::endl;
    }

    if (response_max_data_length >= 3) {  // Prevent overflow
        response_data[0] = 0xAA;
        response_data[1] = 0xBB;
        response_data[2] = 0xCC;
        *response_data_length = 3;
    }
}

int main(void){
    scrutiny::Config config;
    config.set_buffers(
        scrutiny_rx_buffer, sizeof(scrutiny_rx_buffer),     // Receive
        scrutiny_tx_buffer, sizeof(scrutiny_tx_buffer)      // Transmit 
        );

    // ==== User Command callback! ======
    config.set_user_command_callback(my_user_command_callback);
    // ==================================

    scrutiny::MainHandler scrutiny_main;
    scrutiny_main.init(&config);
    
    uint32_t last_timestamp = get_timestamp_microsec();
    while(true){
        uint32_t const timestamp = get_timestamp_microsec();
        // ... 
        // ...
        uint32_t const time_delta = (timestamp-last_timestamp);
        scrutiny_main.process( time_delta*10U );  // Timesteps are multiples of 100ns
        last_timestamp = timestamp;
    }
}
