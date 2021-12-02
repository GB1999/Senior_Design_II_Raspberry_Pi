from __future__ import division

import re
import sys

from google.cloud import speech
from googletrans import Translator

import pyaudio
from six.moves import queue

# Audio recording parameters
RATE = 44100
CHUNK = int(RATE / 10)  # 100ms

language_code = "en-US"

import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="/home/pi/Documents/APIs/senior-design-ii-333805-7f6558f8e86a.json"

class MicrophoneStream(object):
    """Opens a recording stream as a generator yielding the audio chunks."""

    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1,
            rate=self._rate,
            input=True,
            frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b"".join(data)




class TranscriptionService:
    def __init__(self):
        self.translator = Translator()
        self.selected_language = "en"
        
    def listen_print_loop(self, responses, transcript_buffer, lang_buffer):
        num_chars_printed = 0
        for response in responses:
            #print(response)
            if not response.results:
                continue

            # The `results` list is consecutive. For streaming, we only care about
            # the first result being considered, since once it's `is_final`, it
            # moves on to considering the next utterance.
            result = response.results[0]
            if not result.alternatives:
                continue

            # Display the transcription of the top alternative.
            transcript = result.alternatives[0].transcript
            confidence = result.alternatives[0].confidence
            time_elapsed = result.result_end_time

            if result.is_final:
                if not lang_buffer.empty():
                        self.selected_language = lang_buffer.get()
                        
                if self.selected_language != "en":
                    print(f'translating to {self.selected_language}')
                    translated_transcript = self.translator.translate(transcript, dest=self.selected_language).text
                    print(translated_transcript)
                    transcript_buffer.put((translated_transcript, confidence))
                    
                else:
                    print(f'{transcript} took {time_elapsed} to transcribe')

                    transcript_buffer.put((transcript, confidence))

                    num_chars_printed = 0
            
    def run(self, transcript_buffer, lang_buffer):
        # See http://g.co/cloud/speech/docs/languages
        # for a list of supported languages.
          # a BCP-47 language tag
        data_buff = queue
        client = speech.SpeechClient()
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=RATE,
            language_code=language_code,
        )

        streaming_config = speech.StreamingRecognitionConfig(
            config=config, interim_results=True
        )

        with MicrophoneStream(RATE, CHUNK) as stream:
            audio_generator = stream.generator()
            requests = (
                speech.StreamingRecognizeRequest(audio_content=content)
                for content in audio_generator
            )

            responses = client.streaming_recognize(streaming_config, requests)

            # Now, put the transcription responses to use.
            self.listen_print_loop(responses, transcript_buffer, lang_buffer)


