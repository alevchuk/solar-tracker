#define BYTE_TO_BINARY_PATTERN "%c%c%c%c %c%c%c%c"
#define BYTE_TO_BINARY(byte)  \
  (byte & 0x80 ? '1' : '0'), \
  (byte & 0x40 ? '1' : '0'), \
  (byte & 0x20 ? '1' : '0'), \
  (byte & 0x10 ? '1' : '0'), \
  (byte & 0x08 ? '1' : '0'), \
  (byte & 0x04 ? '1' : '0'), \
  (byte & 0x02 ? '1' : '0'), \
  (byte & 0x01 ? '1' : '0') 

#include <stdio.h>
#include <pigpio.h>
#include <time.h>
#include <math.h>
#include <string.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <pthread.h>

// the following is needed for the TCP server
#include <stdio.h> // standard input and output library
#include <stdlib.h> // this includes functions regarding memory allocation
#include <string.h> // contains string functions
#include <errno.h> //It defines macros for reporting and retrieving error conditions through error codes
#include <time.h> //contains various functions for manipulating date and time
#include <unistd.h> //contains various constants
#include <sys/types.h> //contains a number of basic derived types that should be used whenever appropriate
#include <arpa/inet.h> // defines in_addr structure
#include <sys/socket.h> // for socket creation
#include <netinet/in.h> //contains constants and structures needed for internet domain addresses


#define DATA_FORMAT   0x31  // data format register address
#define DATA_FORMAT_B 0x0B  // data format bytes: +/- 16g range, 13-bit resolution (p. 26 of ADXL345 datasheet)
#define READ_BIT      0x80
#define MULTI_BIT     0x40
#define BW_RATE       0x2C
#define POWER_CTL     0x2D
#define DATAX0        0x32

const char SW_Reset[] =   {0xB4, 0x00, 0x20, 0x98};
const char Read_WHOAMI[] =   {0x40, 0x00, 0x00, 0x91};
const char Read_ACC_X[] =   {0x04, 0x00, 0x00, 0xF7};
const char Read_ACC_Y[] =   {0x08, 0x00, 0x00, 0xFD};
const char Read_ACC_Z[] =   {0x0C, 0x00, 0x00, 0xFB};
const char Read_STO[] =       {0x10, 0x00, 0x00, 0xE9};
const char Read_Temperature[] = {0x14, 0x00, 0x00, 0xEF};
const char Change_to_mode_1[] = {0xB4, 0x00, 0x00, 0x1F};
const char Change_to_mode_2[] = {0xB4, 0x00, 0x01, 0x02};
const char Change_to_mode_3[] = {0xB4, 0x00, 0x02, 0x25};
const char Change_to_mode_4[] = {0xB4, 0x00, 0x03, 0x38};
const char Read_Status_Summary[] =  {0x18, 0x00, 0x00, 0xE5};

// Register Addresses
const char ACC_X  =  0x01;
const char ACC_Y  =  0x02;
const char ACC_Z  =  0x03;
const char STO    =  0x04;
const char TEMP   =  0x05;
const char STATUS =  0x06;
const char MODE   =  0x0D;
const char WHOAMI =  0x10;
const char SELBANK = 0x1F;

// Read speed: 1-100, percentage of max ODR speed.
// 100 = full 2 kHz (read every 0.5ms), 50 = 1 kHz, 10 = 200 Hz, etc.
#define READ_SPEED_PCT 100

// Server
const int PORT = 2017;

// Accumulator for continuous sensor reads — uses int64_t to avoid overflow.
// At 2 kHz for 60s = 120,000 samples; max sum = 120k * 32767 = 3.93 billion,
// which exceeds int32_t range (2.15 billion). int64_t handles this safely.
typedef struct {
    int64_t sum_x, sum_y, sum_z;
    int64_t sum_temp;
    uint32_t count;
    short last_sto;
    pthread_mutex_t mutex;
} accumulator_t;

static accumulator_t g_acc = {
    .sum_x = 0, .sum_y = 0, .sum_z = 0,
    .sum_temp = 0, .count = 0, .last_sto = -100,
    .mutex = PTHREAD_MUTEX_INITIALIZER
};

static uint8_t CRC8(uint8_t BitValue, uint8_t CRC)
{
  uint8_t Temp;
  Temp = (uint8_t)(CRC & 0x80);
  if (BitValue == 0x01)
  {
    Temp ^= 0x80;
  }
  CRC <<= 1;
  if (Temp > 0)
  {
    CRC ^= 0x1D;
  }
  return CRC;
}

// Calculate CRC for 24 MSB's of the 32 bit dword
// (8 LSB's are the CRC field and are not included in CRC calculation)
uint8_t CalculateCRC(uint32_t Data)
{
  uint8_t BitIndex;
  uint8_t BitValue;
  uint8_t CRC;
  CRC = 0xFF;
  for (BitIndex = 31; BitIndex > 7; BitIndex--)
  {
    BitValue = (uint8_t)((Data >> BitIndex) & 0x01);
    CRC = CRC8(BitValue, CRC);
  }
  CRC = (uint8_t)~CRC;
  return CRC;
}


void printBytes(char data[], int len) {
    printf("Got data: \n");
    for(int i = 0; i < len; ++i) {
            printf("byte %d: "BYTE_TO_BINARY_PATTERN" ", i, BYTE_TO_BINARY(data[i]));
        printf("%02X\n", data[i]);
    }
}

void printCommand(char data[], int len) {
    printf(BYTE_TO_BINARY_PATTERN, BYTE_TO_BINARY(data[0]));
    printf(" %02X\n", data[0]);
}

// 6000 LSB/g
const int MODE1_SENSITIVITY = 6000;
const int MODE2_SENSITIVITY = 3000;
const int MODE3_SENSITIVITY = 12000;
const int MODE4_SENSITIVITY = 12000;
const int MODE1_HZ = 40;
const int MODE2_HZ = 70;
const int MODE3_HZ = 10;
const int MODE4_HZ = 10;
const int speedSPI = 2000000;  // SPI communication speed, 2 MHz per datasheet Table 8 recommendation

// Global status
int stats_frame_count = 0;
int stats_crc_ok_count = 0;
int stats_temperature = -1000;
bool first_read = true;
short x_0, y_0, z_0;
double len_0;

void readSPIFrame(int h, const char next_cmd[], uint8_t* rw, uint8_t* addr, uint8_t* rs, uint8_t* data1, uint8_t* data2, bool* crc_ok) {
  // this is according to datasheet_scl3300-d01 section 5.1.3 "SPI frame"
  char data[4], cmd[4];

  time_sleep(10e-6);  // 10µs minimum inter-frame gap (TLH), datasheet Table 8

  memcpy(cmd, next_cmd, 4);
  spiXfer(h, cmd, data, 4);

  *rw = data[0]>>7;

  *addr = (data[0] & 0b01111100)>>2;
  *rs =   (data[0] & 0b00000011);

  *data1 = (uint8_t)data[1];
  *data2 = (uint8_t)data[2];

  uint32_t first24bits = (uint8_t)data[0]<<24 | ((uint8_t)data[1]<<16) | ((uint8_t)data[2]<<8);
  // printf("first 24: %06X\n", first24bits);

  // printf("CRC calculated: %02X\n", CalculateCRC(first24bits));
  // printf("CRC from sensor: %02X\n", data[3]);
  // // printf("CRC calculated: "BYTE_TO_BINARY_PATTERN"\n", BYTE_TO_BINARY(CalculateCRC(first24bits)));
  // // printf("CRC from sensor: "BYTE_TO_BINARY_PATTERN"\n", BYTE_TO_BINARY(data[3]));
  
  stats_frame_count++;
  if (data[3] == CalculateCRC(first24bits)) {
    stats_crc_ok_count++;
    *crc_ok = true;
  } else {
    *crc_ok = false;
  }
}

void printSPIFrame(uint8_t rw, uint8_t addr, uint8_t rs, uint8_t data1, uint8_t data2, bool crc_ok) {
  printf("SPI Frame: ");
  if (rw == 1) {
    printf("W");
  } else {
    printf("R");
  }

  printf(" ");
  if        (addr ==  ACC_X )
     printf(    "     ACC_X");

  else if   (addr ==  ACC_Y )
     printf(    "     ACC_Y");

  else if   (addr ==  ACC_Z )
     printf(    "     ACC_Z");

  else if   (addr ==   MODE )
     printf(    "      MODE");

  else if   (addr == WHOAMI )
     printf(    "    WHOAMI");

  else if  (addr == SELBANK )
     printf(    "   SELBANK");

  else if   (addr == STATUS )
     printf(    "    STATUS");

  else if      (addr == STO )
     printf(    "       STO");


  else {
     // printf("%02X ", addr);
     // printf("byte: "BYTE_TO_BINARY_PATTERN" ", BYTE_TO_BINARY(addr));
     printf(    "  NEW_ADDR");
  }

  printf(" ");
  if (rs == 0b00000000)
    printf("Startup_in_progress...");
  else if (rs == 0b00000001)
    printf("Normal");
  else if (rs == 0b00000010)
    printf("   N/A");
  else if (rs == 0b00000011)
    printf(" Error");

  printf(" ");
  printf("[data: %02X %02X]", data1, data2);

  printf(" ");
  if (crc_ok) {
    printf("[crc_ok]");
  } else {
    printf("[CRC_CORRUPTED]");
  }

  printf("\n");
}

void writeOnly(int h, const char next_command_hint[]) {
  bool crc_ok;
  uint8_t rw, addr, rs;
  uint8_t data1, data2;

  readSPIFrame(h, next_command_hint, &rw, &addr, &rs, &data1, &data2, &crc_ok);
}

short readAcc(int h, const char command[], const char next_command_hint[]) {
  short retval;

  bool crc_ok;
  uint8_t rw, addr, rs;
  uint8_t data1, data2;

  readSPIFrame(h, next_command_hint, &rw, &addr, &rs, &data1, &data2, &crc_ok);
  if (crc_ok) {
    // printSPIFrame(rw, addr, rs, data1, data2, crc_ok);

    if (
      ( command == Read_ACC_X && addr == ACC_X ) ||
      ( command == Read_ACC_Y && addr == ACC_Y ) ||
      ( command == Read_ACC_Z && addr == ACC_Z )
    ) {
        retval = (data1 << 8) | data2;
        return retval;
    }
  }

  return -100;
}

short readTemperature(int h, const char next_command_hint[]) {
  short retval;

  bool crc_ok;
  uint8_t rw, addr, rs;
  uint8_t data1, data2;

  readSPIFrame(h, next_command_hint, &rw, &addr, &rs, &data1, &data2, &crc_ok);
  if (crc_ok) {
    if (addr == TEMP) {
        retval = (data1 << 8) | data2;
        return retval;
    }
  }

  return -1000;
}

short readSTO(int h, const char next_command_hint[]) {
  short retval;

  bool crc_ok;
  uint8_t rw, addr, rs;
  uint8_t data1, data2;

  readSPIFrame(h, next_command_hint, &rw, &addr, &rs, &data1, &data2, &crc_ok);
  if (crc_ok) {
    // printSPIFrame(rw, addr, rs, data1, data2, crc_ok);

    if (addr == STO) {
        retval = (data1 << 8) | data2;
        return retval;
    }
  }

  return -100;
}

void setMode4(int h) {
  bool crc_ok;
  uint8_t rw, addr, rs;
  uint8_t data1, data2;

  while (true) {
    readSPIFrame(h, SW_Reset, &rw, &addr, &rs, &data1, &data2, &crc_ok);
    time_sleep(1.0 / 1000);  // 1 ms, as per recommeded startup sequence, Table 11, Step 1.2
    // Change to MODE 4: Inclination mode
    // 10 Hz 1st order low pass filter
    // Low noise mode, 12000 LSB/g, ±10° range
    readSPIFrame(h, Change_to_mode_4, &rw, &addr, &rs, &data1, &data2, &crc_ok);
    if (!crc_ok) {
      continue;
    }
    time_sleep(100.0 / 1000);  // 100 ms, as per recommeded startup sequence, Table 11, Step 6

    readSPIFrame(h, Read_Status_Summary, &rw, &addr, &rs, &data1, &data2, &crc_ok);
    time_sleep(1.0 / MODE4_HZ);

    while (true) {
      readSPIFrame(h, Read_Status_Summary, &rw, &addr, &rs, &data1, &data2, &crc_ok);
      time_sleep(1.0 / MODE4_HZ);
      if (crc_ok) {
        // printSPIFrame(rw, addr, rs, data1, data2, crc_ok);
        if (rs == 0b00000001) {
            return;
        }
      }
    }
  }
}

// Background thread: continuously reads sensor at ODR to maintain noise performance
// (datasheet section 4.1) and accumulates samples for averaging.
void *reader_thread(void *arg) {
  int h = *(int *)arg;
  // delay_us = 500µs * (100 / READ_SPEED_PCT)
  // At READ_SPEED_PCT=100: 500µs = 2 kHz (full ODR)
  double delay_s = 500e-6 * 100.0 / READ_SPEED_PCT;

  while (true) {
    short x = -100, y = -100, z = -100, sto = -100, temp_raw = -1000;

    // read X
    writeOnly(h, Read_ACC_X);
    x = readAcc(h, Read_ACC_X, Read_ACC_Y);

    // read Y
    writeOnly(h, Read_ACC_Y);
    y = readAcc(h, Read_ACC_Y, Read_ACC_Z);

    // read Z
    writeOnly(h, Read_ACC_Z);
    z = readAcc(h, Read_ACC_Z, Read_STO);

    // read STO
    writeOnly(h, Read_STO);
    sto = readSTO(h, Read_Temperature);

    // read Temperature
    writeOnly(h, Read_Temperature);
    temp_raw = readTemperature(h, Read_ACC_X);

    // Only accumulate if all reads succeeded
    if (x != -100 && y != -100 && z != -100 && temp_raw != -1000) {
      pthread_mutex_lock(&g_acc.mutex);
      g_acc.sum_x += x;
      g_acc.sum_y += y;
      g_acc.sum_z += z;
      g_acc.sum_temp += temp_raw;
      g_acc.count++;
      if (sto != -100) {
        g_acc.last_sto = sto;
      }
      pthread_mutex_unlock(&g_acc.mutex);
    }

    time_sleep(delay_s);
  }
  return NULL;
}

void collectSensorData(char *dataSending, size_t dataCapacity) {
	char* p = dataSending;
	char* end = dataSending + dataCapacity;
	int n = 0;

  // Snapshot accumulated samples and reset
  int64_t snap_x, snap_y, snap_z, snap_temp;
  uint32_t snap_count;
  short snap_sto;

  pthread_mutex_lock(&g_acc.mutex);
  snap_x = g_acc.sum_x;
  snap_y = g_acc.sum_y;
  snap_z = g_acc.sum_z;
  snap_temp = g_acc.sum_temp;
  snap_count = g_acc.count;
  snap_sto = g_acc.last_sto;
  g_acc.sum_x = 0;
  g_acc.sum_y = 0;
  g_acc.sum_z = 0;
  g_acc.sum_temp = 0;
  g_acc.count = 0;
  pthread_mutex_unlock(&g_acc.mutex);

  if (snap_count == 0) {
    snprintf(dataSending, dataCapacity, "ERROR: no samples accumulated yet\n");
    return;
  }

  // Average using double to preserve precision
  double avg_x = (double)snap_x / snap_count;
  double avg_y = (double)snap_y / snap_count;
  double avg_z = (double)snap_z / snap_count;
  double avg_temp_raw = (double)snap_temp / snap_count;

  // Convert temperature: section 2.4 of datasheet
  double temp_celsius = -273.0 + (avg_temp_raw / 18.9);

	double len;
  double angle, angle_deg;

  if (first_read) {
      x_0 = (short)(avg_x + 0.5);
      y_0 = (short)(avg_y + 0.5);
      z_0 = (short)(avg_z + 0.5);
      len_0 = sqrt(pow(x_0, 2) + pow(y_0, 2) + pow(z_0, 2));
      first_read = false;
  }
  len = sqrt(avg_x * avg_x + avg_y * avg_y + avg_z * avg_z);
  angle = acos((x_0 * avg_x + y_0 * avg_y + z_0 * avg_z) / (len_0 * len));
  angle_deg = angle * (180.0 / M_PI);

  n = snprintf(p, dataCapacity, "%f\t", time_time());
	p += n; dataCapacity -= n;

  n = snprintf(p, dataCapacity, "%f\t", avg_x / MODE4_SENSITIVITY);
	p += n; dataCapacity -= n;

  n = snprintf(p, dataCapacity, "%f\t", avg_y / MODE4_SENSITIVITY);
	p += n; dataCapacity -= n;

  n = snprintf(p, dataCapacity, "%f\t", avg_z / MODE4_SENSITIVITY);
	p += n; dataCapacity -= n;

  n = snprintf(p, dataCapacity, "%f\t", angle_deg);
	p += n; dataCapacity -= n;

  n = snprintf(p, dataCapacity, "%.2f\t", (float)stats_crc_ok_count/(float)stats_frame_count);
	p += n; dataCapacity -= n;

  n = snprintf(p, dataCapacity, "%d\t", snap_sto);
	p += n; dataCapacity -= n;

  n = snprintf(p, dataCapacity, "%.2f", temp_celsius);
	p += n; dataCapacity -= n;

  n = snprintf(p, dataCapacity, "\n");
	p += n; dataCapacity -= n;

	if (p >= end) {
		printf("ERROR: trying to write too much data to the nework\n");
		exit(1);
	}

  printf("angle=%f samples=%u\n", angle_deg, snap_count);
}

void swResetAndCheck(int h) {
  // according to scl3300-d01 datasheet, the recommended startup
  // sequence is the do sw reset and then read status until
  // proper startup is confirmed. Instead we just read WHOAMI

  bool crc_ok;
  uint8_t rw, addr, rs;
  uint8_t data1, data2;

  setMode4(h);
  time_sleep(1.0 / MODE4_HZ);


  // WHOAMI
  for (int i = 0; i < 100; ++i) {
    readSPIFrame(h, Read_WHOAMI, &rw, &addr, &rs, &data1, &data2, &crc_ok);
    // printSPIFrame(rw, addr, rs, data1, data2, crc_ok);

    if (data2 == 0xC1) {
      return;
    }
    time_sleep(1.0 / MODE4_HZ);
  }

  printf("ERROR: can't communicated to SPI device, "
    "no WHOAMI or WHOAMI is incorrect after many retires");

  exit(1);
}

int main(int argc, char *argv[]) {

		// start TCP server
		char dataSending[1025]; // Actually this is called packet in Network Communication, which contain data and send through.
		int clintListn = 0, clintConnt = 0;
		struct sockaddr_in ipOfServer;
		clintListn = socket(AF_INET, SOCK_STREAM, 0); // creating socket
		memset(&ipOfServer, '0', sizeof(ipOfServer));
		memset(dataSending, '0', sizeof(dataSending));
		ipOfServer.sin_family = AF_INET;
		ipOfServer.sin_addr.s_addr = htonl(INADDR_ANY);
		ipOfServer.sin_port = htons(PORT); // this is the port number of running server
		bind(clintListn, (struct sockaddr*)&ipOfServer , sizeof(ipOfServer));
		listen(clintListn , 20);


    // read sensor data for ever TCP request

    int h;

    // SPI sensor setup
    if (gpioInitialise() < 0) {
        printf("Failed to initialize GPIO!");
        return 1;
    }

    h = spiOpen(0, speedSPI, 0);

    swResetAndCheck(h);

    // Launch background reader thread
    pthread_t reader_tid;
    if (pthread_create(&reader_tid, NULL, reader_thread, &h) != 0) {
        printf("Failed to create reader thread!\n");
        return 1;
    }
    pthread_detach(reader_tid);

		printf("Listening on port %d, reader at %d%% ODR speed\n", PORT, READ_SPEED_PCT);
		while (true) {
				clintConnt = accept(clintListn, (struct sockaddr*)NULL, NULL);
				collectSensorData(&dataSending[0], 1025);
				write(clintConnt, dataSending, strlen(dataSending));

        close(clintConnt);

    }
    
    gpioTerminate();

    return 0;
}
