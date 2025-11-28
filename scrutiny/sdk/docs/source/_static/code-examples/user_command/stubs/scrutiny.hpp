    
#include <cstdint>
#include <cstddef>

typedef void (*scrutiny_c_user_command_callback_t)(
    uint8_t const subfunction,
    uint8_t const *request_data,
    uint16_t const request_data_length,
    uint8_t *response_data,
    uint16_t *response_data_length,
    uint16_t const response_max_data_length);

namespace scrutiny {
    class Config
    {
        public:
        void set_buffers(uint8_t *, size_t, uint8_t *, size_t);
        void set_user_command_callback(scrutiny_c_user_command_callback_t);
    };

    class MainHandler
    {
        public:
        void init(Config* config);
        void process(uint32_t timestemp);
    };
}
