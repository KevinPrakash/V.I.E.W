import os
import time
import subprocess
import cv2

from Initial import Main
import Maps
from OCR import ocr

if __name__=="__main__":
        start = Main()
        maps = Maps.Maps()
        start.tts("welcome back")
        while True:
            start.tts("Choose a function")
            operation = start.stt("shortanswer")
            if operation in start.getcommand("maps"):
                maps.mapsloop()
            elif operation in start.getcommand("facerec"):
                start.writefunction("f")
                while (not (start.readfunction()=="a")):
                        time.sleep(0.1) //delay
                start.writefunction("r")
                start.modeluse = True
            elif operation in start.getcommand("ocr"):
                start.writefunction("f")
                time.sleep(1)
                img = cv2.imread("./frame.jpg")
                output = ocr(img)
                read_short = output.split("\n")
                start.tts(",".join(read_short[0:start.getconfig("minreadlines")]))
                if len(read_short) > 2:
                        start.tts("Continue")
                        operation = start.stt("veryshortanswer")
                else:
                        operation = "no"
                if operation == "yes":
                    for i in range(start.getconfig("minreadlines"),len(read_short)):
                        start.tts(read_short[i])     
            elif operation in start.getcommand("caption"):
                start.writefunction("f")
                while (not (start.readfunction()=="a")):
                        time.sleep(0.1)
                start.writefunction("c")
                start.modeluse = True
            elif operation in start.getcommand("config"):
                start.loadconfig()
            elif operation in start.getcommand("voices"):
                start.loadvoice()
            elif operation in start.getcommand("exit"):
                start.writefunction("q")
                start.tts("goodbye")
                exit()
            elif operation in start.getcommand("help"):
                start.tts("available commands are maps,facerec,ocr,caption,config,voices,exit")
            else:
                start.tts("retry")
            if start.modeluse:
                if os.path.isfile("./Output.txt") and start.readfunction()=="a":
                    f = open("./Output.txt","r")
                    output = f.readlines()[0]
                    f.close()
                    start.tts(output)
                    os.remove("./Output.txt")
                    start.modeluse = False
                        
                    

