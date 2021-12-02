from kivy.app import App
from kivy.clock import Clock
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label

import socket  
import time, logging
from datetime import datetime
import threading, collections, queue, os, os.path
import numpy as np
import pyaudio
import wave
#import webrtcvad
#from halo import Halo
#from scipy import signal
from transcription_service import *
from gatt_server import *
import json


logging.basicConfig(level=20)



transcript_queue = queue.Queue()
app_queue = queue.Queue()
language_queue = queue.Queue()

start_time = 0


                    
class DisplayScreen(Widget):
    def update(self,dt):
        # create variables for labels
        if not transcript_queue.empty():
            message, confidence = transcript_queue.get()
            self.ids.transcription_label.text = message
            #self.ids.transcription_label.color = [0,abs(int(confidence))/100,0,1]
            self.ids.confidence_label.text = "CONFIDENCE: {:0.4f}%".format(confidence*100)
            print(type(confidence))
            print(confidence)
            print(int(confidence))
        if not app_queue.empty():
            update_dict = app_queue.get()
            self.ids.transcription_label.font_size = int(update_dict['font_size'])
            print(update_dict['bg_color'], "has type", type(update_dict['bg_color']))
            self.rgba = update_dict['bg_color']
            #self.ids.confidence_label.color = (.5,.2,.1,1)

class TestScreen(GridLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cols = 2
        self.add_widget(Label(text = "IP"))

class TranscriptionApp(App):
    def build(self):
        screen = DisplayScreen()
        Clock.schedule_interval(screen.update,1.0/10.0)
        return screen

def RunKivyApp():
    TranscriptionApp().run()

def RunServer():
    app = Application()
    #app.add_service(ThermometerService(0))
    #app.add_service(ThermometerService(0))
    app.add_service(AirHumidityTempService(0))
    app.add_service(FanService(1))
    app.add_service(VolumeService(2))
    app.add_service(LanguageSelectionService(3, language_queue))
    app.register()

    adv = ThermometerAdvertisement(0)
    adv.register()

    try:
        app.run()
    except KeyboardInterrupt:
        app.quit()
    pass
   
def RunTranscription():
    ts = TranscriptionService()
    ts.run(transcript_queue, language_queue)

def main():
    
    p1 = threading.Thread(target = RunTranscription)
    p2 = threading.Thread(target = RunKivyApp)
    p0 = threading.Thread(target = RunServer)
    
    p0.start()
    p2.start()
    p1.start()
    
    
    
 

if __name__ == '__main__':

    DEFAULT_SAMPLE_RATE = 16000
    main()
