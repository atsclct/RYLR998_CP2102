import asyncio
import serial_asyncio

class Packet:
    def __init__(self, data, addr=0, rssi=0, snr=0):
        self.data = data
        self.addr = addr
        self.rssi = rssi
        self.snr = snr

    def __str__(self):
        return self.data

class RYLR(asyncio.Protocol):
    def __init__(self):
        self.transport = None
        self._packet = None
        self._resp = None
        self.buffer = b''  # Initialize the buffer to hold incoming data fragments
        self._waiting = []
        self._frequency = 915.0  # Default settings
        self._bandwidth = 250000
        self._spreading_factor = 10
        self._coding_rate = 8
        self._preamble_length = 4
        
    def connection_made(self, transport):
        self.transport = transport
        print('Serial connection established')
        # Get the current running loop and schedule initialization
        loop = asyncio.get_running_loop()
        loop.create_task(self.init())


    def data_received(self, data):
        self.buffer += data  # Append received data to the buffer
        if b'\r\n' in self.buffer:
            # Split buffer by lines and process each line that ends with \r\n
            lines = self.buffer.split(b'\r\n')
            self.buffer = lines.pop()  # Anything after the last \r\n is incomplete and goes back to the buffer

            for line in lines:
                self.process_complete_message(line.decode())

    def process_complete_message(self, message):
        #print(f"Processing message: {message}")  # For debugging
        # Here you process your complete message as before
        if message.startswith('+RCV='):
            self._recv(message[5:])
        else:
            self._resp = message
            if self._waiting:
                e = self._waiting.pop(0)
                e.set()
                
    def connection_lost(self, exc):
        print('The serial connection was lost:', exc)

    async def _cmd(self, cmd):
        self.transport.write(cmd.encode('utf-8') + b'\r\n')
        event = asyncio.Event()
        self._waiting.append(event)
        await event.wait()
        return self._resp

    async def init(self):
        await self.set_frequency(self._frequency)
        await self._set_parameters()

    async def send(self, msg, addr=0):
        await self._cmd(f'AT+SEND={addr},{len(msg)},{msg}')

    async def recv_packet(self):
        while self._packet is None:
            await asyncio.sleep(0.1)
        pkt = self._packet
        self._packet = None
        return pkt

    async def get_baud_rate(self):
        resp = await self._cmd('AT+IPR?')
        return int(resp[5:])

    async def set_baud_rate(self, baud_rate):
        await self._cmd(f'AT+IPR={baud_rate}')

    async def get_frequency(self):
        resp = await self._cmd('AT+BAND?')
        return int(resp[6:]) / 1000000.0

    async def set_frequency(self, frequency):
        await self._cmd(f'AT+BAND={int(frequency * 1000000)}')

    async def get_address(self):
        resp = await self._cmd('AT+ADDRESS?')
        return int(resp[9:])

    async def set_address(self, addr):
        await self._cmd(f'AT+ADDRESS={addr}')

    async def _set_parameters(self):
        sf = self._spreading_factor
        bw = next((i for i, b in enumerate((7800, 10400, 15600, 20800, 31250, 41700, 62500, 125000, 250000)) if self._bandwidth <= b), 8)
        cr = self._coding_rate - 4
        pl = self._preamble_length
        await self._cmd(f'AT+PARAMETER={sf},{bw},{cr},{pl}')

    def _recv(self, x):
        #print(x)
        try:
            data_parts = x.split(',')
            n=len(data_parts)
            addr=data_parts[0]
            #n = int(data_parts[1]  # expected number of data parts after n
            data = ','.join(data_parts[2:n-2])  # reassemble data assuming 'n' is count of parts
            snr = data_parts[n-1]  # rssi and snr are immediately after data
            rssi = data_parts[n-2]  # rssi and snr are immediately after data
            self._packet = Packet(data, int(addr), int(rssi), int(snr))
        except ValueError as e:
            print(f"Error parsing received data: {e}")
            self._packet = None


    async def init(self):
        await asyncio.sleep(1)  # Delay to ensure settings can be applied
        await self.set_frequency(self._frequency)
        await self._set_parameters()

# Main routine adapted for the correct initialization
async def main():
    loop = asyncio.get_event_loop()
    # Setup serial connection parameters directly here
    transport, protocol = await serial_asyncio.create_serial_connection(
        loop, RYLR, '/dev/tty.usbserial-14210', baudrate=115200
    )

    # Perform operations after ensuring protocol is fully ready
    await asyncio.sleep(2)  # Wait for the device to be fully ready
    await protocol.send("Hello LoRa", addr=1)
    while True:
        packet = await protocol.recv_packet()
        print(packet)

if __name__ == "__main__":
    asyncio.run(main())