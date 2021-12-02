import websockets
import asyncio
import base64
import json
import pyaudio


class TranscriptionService:
    def __init__(self):
        self.auth_key = "9aaa3096eb9141908dbfb72a7d8ac8c3"
        # the AssemblyAI endpoint we're going to hit
        self.URL = "wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000"

        self.FRAMES_PER_BUFFER = 3200
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        p = pyaudio.PyAudio()

        # starts
        # create instance of pyaudio stream to capture audio frames
        self.stream = p.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.FRAMES_PER_BUFFER
        )


    async def send_receive(self, queue):
        print(f'Connecting websocket to url ${self.URL}')
        async with websockets.connect(
                self.URL,
                extra_headers=(("Authorization", self.auth_key),),
                ping_interval=5,
                ping_timeout=20
        ) as _ws:
            await asyncio.sleep(0.1)
            print("Receiving SessionBegins ...")
            session_begins = await _ws.recv()
            print(session_begins)
            print("Sending messages ...")

            async def send():
                while True:
                    try:
                        # capture audio frames from pyaudio stream
                        data = self.stream.read(self.FRAMES_PER_BUFFER, exception_on_overflow = False)
                        # encode audio capture as unicode
                        data = base64.b64encode(data).decode("utf-8")
                        json_data = json.dumps({"audio_data": str(data)})
                        # send ecoded audio data to websocket
                        await _ws.send(json_data)
                    except websockets.exceptions.ConnectionClosedError as e:
                        print(e)
                        assert e.code == 4008
                        break
                    except Exception as e:
                        print(e)
                        assert False, "Not a websocket 4008 error"
                    await asyncio.sleep(0.01)

                return True

            async def receive():
                while True:
                    try:
                        result_str = await _ws.recv()
                        result_json = json.loads(result_str)
                        if result_json['message_type'] == "FinalTranscript":
                            queue.put((result_json['text'],result_json['confidence']))
                            #print(result_json)
                        #print(result_str)
                        #print(json.loads(result_str)['text'])
                    except websockets.exceptions.ConnectionClosedError as e:
                        print(e)
                        assert e.code == 4008
                        break
                    except Exception as e:
                        assert False, "Not a websocket 4008 error"

            send_result, receive_result = await asyncio.gather(send(), receive())
            
    def run(self, queue):
        asyncio.run(self.send_receive(queue))