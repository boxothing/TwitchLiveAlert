#!/usr/bin/env python3

import sys, signal
import win32api,win32process,win32con
import configparser
import msvcrt
import os
from os import makedirs
from os.path import isfile, join, exists, dirname, abspath
import requests
import json
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import time
from datetime import datetime, timedelta
from html import escape
from urllib.parse import quote
import threading
import re
import zroya
import webbrowser
import traceback

# Thread safe print
def safeprint(*args, **kwargs):
  with printLock:
    print(*args, **kwargs)

# Handle system interrupt to break python loop scope
def signalHandler(signal, frame):
    threads = [t for t in threading.enumerate() if t.name != "MainThread"]

    if threads:
        safeprint("\nKeyboard interrupt: Stopping {0} thread{1} before main thread ...".format(len(threads), "s" if len(threads) != 1 else ""))

        for t in threads:
            t.stop()
        for t in threads:
            t.join()

    sys.exit()

# Pause and exit on key press
def exitOnKey():
    safeprint("아무 키나 누르면 종료됩니다 ...")
    msvcrt.getch()
    sys.exit()

# Get absolute path to resource, works for dev and for PyInstaller
def resourcePath(relPath):
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        basePath = sys._MEIPASS
    except Exception:
        basePath = abspath(".")

    return join(basePath, relPath)

def setpriority(pid=None,priority=1):
    # Set priority between 0-5 where 2 is normal priority.

    priorityclasses = [win32process.IDLE_PRIORITY_CLASS,
                       win32process.BELOW_NORMAL_PRIORITY_CLASS,
                       win32process.NORMAL_PRIORITY_CLASS,
                       win32process.ABOVE_NORMAL_PRIORITY_CLASS,
                       win32process.HIGH_PRIORITY_CLASS,
                       win32process.REALTIME_PRIORITY_CLASS]
    if pid == None:
        pid = win32api.GetCurrentProcessId()

    handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
    win32process.SetPriorityClass(handle, priorityclasses[priority])

# Print current date and time
def timeStamp(format = None):
    now = datetime.now()

    if format is None:
        format = "[%y-%m-%d %H:%M:%S]"

    date_string = now.strftime(format)

    return date_string

# Returns valid API response
def getAPIResponse(url, clientID=None, kraken=None, token=None, ignoreHeader=None, data=None, printError=None, post=None, raw=None, ignoreKrakenHeader=None, insecure=None):
    global needOAuthUpdate
    header = None

    if not ignoreHeader:
        header = {}

        if kraken: # Extra header for Kraken API
            if not ignoreKrakenHeader:
                header.update({'Accept' : "application/vnd.twitchtv.v5+json"})

            if clientID: header.update({'Client-ID' : clientID})

            if token:
                header.update({'Authorization' : "OAuth " + token})
        else:
            if clientID: header.update({'Client-ID' : clientID})
            if token: header.update({'Authorization' : "Bearer " + token})

    try:
        if raw:
            if insecure:
                with requests.get(url, timeout=10, verify=False) as res:
                    return res.content
            else:
                with requests.get(url, timeout=10) as res:
                    return res.content
        else:
            if post: # Update data
                res = requests.post(url, data=data, headers=header, timeout=5)
            else: # Request data
                if insecure:
                    res = requests.get(url, headers=header, timeout=10, verify=False)
                else:
                    res = requests.get(url, headers=header, timeout=10)

            # code = res.status_code
            info = res.json()

            if isinstance(threading.current_thread(), threading._MainThread): # Update from main thread only
                if info and info.get("status") == 401: # Must provide a valid Client-ID or OAuth token
                    safeprint("{} Error: {}".format(timeStamp(), info.get("message")))
                    needOAuthUpdate = True

            if not kraken:
                if info.get("data"):
                    return info
            else:
                if info:
                    return info
    except:
        pass

    return b"" if raw else []

# Get OAuth token
def getOAuthToken(clientID, clientSecret):
    filePath = join(dirname(__file__), "oauth.{}".format(clientID))
    url = "https://id.twitch.tv/oauth2/token?client_id={0}&client_secret={1}&grant_type=client_credentials".format(clientID, clientSecret)

    response = getAPIResponse(url, kraken=True, ignoreHeader=True, post=True)

    try:
        # safeprint("{} Fetching new access token...".format(timeStamp()))
        safeprint("{} 새로운 토큰을 발급 받는 중...".format(timeStamp()))

        if response and response.get("access_token"):
            data = json.dumps(response)
            outputFile(filePath, data, mode="w", raw=True)
            # safeprint("{} Successfully grabbed access token!".format(timeStamp()))
            safeprint("{} 성공적으로 새로운 토큰을 받았습니다!".format(timeStamp()))
    except:
        pass

# Returns True if current OAuth token is valid
def validateOAuthToken(clientID):
    filePath = join(dirname(__file__), "oauth.{}".format(clientID))

    try:
        if isfile(filePath):
            content = readFile(filePath, whole=True)
            data = json.loads(content)

            if data:
                token = data.get("access_token")
                # safeprint(token)

                if token:
                    url = "https://id.twitch.tv/oauth2/validate"
                    response = getAPIResponse(url, kraken=True, token=token, ignoreKrakenHeader=True)

                    if response and response.get("client_id"): # OAuth token is valid
                        if response.get("client_id") == clientID:
                            return True
    except:
        return False

    return False

# Returns OAuth access token from file
def setOAuthToken(clientID):
    filePath = join(dirname(__file__), "oauth.{}".format(clientID))

    try:
        if isfile(filePath):
            content = readFile(filePath, whole=True)
            data = json.loads(content)

            if data and data.get("access_token"):
                return data.get("access_token")
    except:
        pass

    return ""

# Returns user clientID using Telegram getUpdates API
def getClientID(botToken):
    if not botToken:
        return

    clientID = ""
    url = "https://api.telegram.org/bot{0}/{1}".format(botToken, "getUpdates")

    res = getAPIResponse(url, kraken=True, ignoreHeader=True)

    if res:
        try:
            clientID = res["result"][0]["message"]["from"]["id"]
        except:
            pass

    return str(clientID)

# Telegram sendMessage API
def sendMessage(botToken, TGclientID, message):
    if not TGclientID:
        return True

    url = "https://api.telegram.org/bot{0}/{1}".format(botToken, "sendMessage")

    data = {
        "chat_id": TGclientID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    res = getAPIResponse(url, kraken=True, ignoreHeader=True, data=data, post=True)

    if res:
        if not res["ok"]:
            if res["error_code"] == 400:
                safeprint("메시지 전달 오류: 설정파일이 잘못되었거나 메시지 호환이 안 됩니다")
            elif res["error_code"] == 403:
                safeprint("메시지 권한 오류: 봇에게 먼저 대화를 걸어주세요")
            else:
                if res.get("error_code"):
                    safeprint("메시지 오류: {}".format(res.get("error_code")))
        else:
            return True

    return False

# Telegram sendPhoto API
def sendPhoto(botToken, TGclientID, photo, caption=""):
    if not TGclientID:
        return True

    url = "https://api.telegram.org/bot{0}/{1}".format(botToken, "sendPhoto")

    data = {
        "chat_id": TGclientID,
        "photo": photo,
        "caption": caption,
        "parse_mode": "HTML"
    }

    res = getAPIResponse(url, kraken=True, ignoreHeader=True, data=data, post=True)

    if res:
        if not res["ok"]:
            if res["error_code"] == 400:
                safeprint("메시지 전달 오류: 설정파일이 잘 못 되었거나 메시지 호환이 안 됩니다")
            elif res["error_code"] == 403:
                safeprint("메시지 권한 오류: 봇에게 먼저 대화를 걸어주세요")
            else:
                if res.get("error_code"):
                    safeprint("메시지 오류: {}".format(res.get("error_code")))
        else:
            return True

    return False

# Convert time from UTC to local
def convertUTCtoLocalTime(timeStr, format="[%y-%m-%d %I:%M:%S %p]"):
    startTime = ""

    try:
        if timeStr:
            if timeStr[-1].lower() == "z": # Strip Z at the end of string
                timeStr = timeStr[:-1]

            startTime = datetime.fromisoformat(timeStr) # Convert to time object
            utc_offset = time.localtime().tm_gmtoff // 3600 # Current local time
            startTime += timedelta(hours=utc_offset) # Local start time

            # Get elapsed time
            currentTime = datetime.now()
            elapsed = currentTime - startTime
            elapsed = time.strftime('%H:%M:%S', time.gmtime(elapsed.total_seconds()))

            startTime = startTime.strftime("[%y-%m-%d %I:%M:%S %p]") # Change format
    except:
        pass

    return [startTime, elapsed]

# Open and read file
def readFile(fileName, mode="r", whole=None):
    try:
        if isfile(fileName):
            with open(fileName, mode, encoding="utf_8_sig") as file:
                text = file.read() if whole else file.readlines()

                if text:
                    return text
                else:
                    return "" if whole else []
    except OSError as e:
        safeprint("Error: " + str(e))

# Output to file
def outputFile(fileName, contents=None, mode="w", raw=None): # Output user list to file
    try:
        directory = dirname(fileName)

        if directory and not exists(directory):
            makedirs(directory)

        if raw:
            with open(fileName, mode) as outfile:
                outfile.write(contents)
        else:
            with open(fileName, mode, encoding="utf-8") as outfile:
                outfile.write(contents)
    except OSError as e:
        safeprint("Error: " + str(e))

# Build list from input file
def fileToList(fileName, removeDuplicate=None):
    listItems = []
    content = readFile(fileName)

    if content:
        listItems = [n.lower() for n in (n.strip().replace("\n", "") for n in content) if n]

        if listItems and removeDuplicate:
            listItems = list(dict.fromkeys(listItems)) # Remove duplicates, order preserved

    return listItems

# Parse Twitch.tv's M3U8 file
def parseM3U8(inputM3U8, excludeURL=None, limit=0): # No leak
    lines = [l for l in inputM3U8.split("\n") if l]
    parsed = {}
    extraKeys = ["#EXT-X-TWITCH-INFO", "#EXT-X-MEDIA", "#EXT-X-STREAM-INF", "#EXT-X-DATERANGE"]
    multiKeys = ["#EXT-X-MEDIA", "#EXT-X-STREAM-INF", "#EXT-X-DATERANGE", "#EXT-X-PROGRAM-DATE-TIME", "#EXTINF", "#EXT-X-TWITCH-PREFETCH"]
    count = 0

    if "#EXTM3U" in lines[0]:
        for n in lines:
            if limit > 0 and limit < count: # Limit parsed line count
                break

            if "#EXTM3U" not in n and n[0] == "#":
                temp = n.split(":", 1) # Split at first colon

                if temp[0] in extraKeys: # Split again for extra options
                    temp2 = [n.split("=") for n in re.split(r',(?=[A-Z])', temp[1].replace('"', ""))] # Split at comma followed by capitalized letter

                    if temp[0] in multiKeys: # Create list for multikeys
                        tempDict = {}

                        for m in temp2:
                            if len(m) > 1:
                                tempDict[m[0]] = m[1]

                        if tempDict:
                            if parsed.get(temp[0]):
                               parsed[temp[0]].append(tempDict)
                            else:
                                parsed[temp[0]] = [tempDict]
                    else:
                        tempDict = {}

                        for m in temp2:
                            if len(m) > 1:
                                tempDict[m[0]] = m[1]
                        if tempDict:
                            parsed[temp[0]] = tempDict
                else:
                    if temp[0] in multiKeys:
                        if parsed.get(temp[0]):
                            parsed[temp[0]].append(temp[1])
                        else:
                            parsed[temp[0]] = [temp[1]]
                    else:
                        parsed[temp[0]] = temp[1]
            elif not excludeURL and n[0:5] == "https":
                if parsed.get("url"):
                    parsed["url"].append(n)
                else:
                    parsed["url"] = [n]

            count += 1

    return parsed

# Get stream data
def getStreamInformation(clientID, loginID, quality="best", streamID=[]):
    tokenURL = "https://api.twitch.tv/api/channels/{0}/access_token.json?client_id={1}&{2}".format(loginID, clientID, int(time.time()))
    sig = ""
    token = getAPIResponse(tokenURL, kraken=True, ignoreHeader=True)
    # safeprint(token)

    try:
        if token and isinstance(token, dict):
            if token.get("error"):
                if token.get("message"): safeprint("{0} Token Error #{1}: {2}".format(timeStamp(), token.get("status"), token.get("message")))
            else:
                sig = token.get("sig", "")
                token = quote(token.get("token", "")) # Convert to url safe string
    except:
        pass

    streamInfo = {}

    if sig and token:
        url = "https://usher.ttvnw.net/api/channel/hls/{0}.m3u8?allow_source=true&fast_bread=true&p={1}&sig={2}&token={3}".format(loginID, int(time.time()), sig, token)

        stream = getAPIResponse(url, ignoreHeader=True, raw=True).decode("utf-8") # Memory leak?
        # safeprint(stream)

        if stream and "#EXTM3U" in stream:
            serverTime = ""
            streamTime = ""
            broadcastID = 0
            source = ""
            sequence = ""
            timeElapsed = ""
            timeTotal = ""
            streamList = parseM3U8(stream)

            if streamList and isinstance(streamList, dict):
                if streamList.get("#EXT-X-TWITCH-INFO"):
                    serverTime = streamList.get("#EXT-X-TWITCH-INFO").get("SERVER-TIME")
                    streamTime = streamList.get("#EXT-X-TWITCH-INFO").get("STREAM-TIME")
                    broadcastID = int(streamList.get("#EXT-X-TWITCH-INFO").get("BROADCAST-ID", 0))

                media = streamList.get("#EXT-X-MEDIA")
                idx = -1

                if media:
                    for i in range(len(media)):
                        if quality == "best":
                            if "chunked" in media[i].get("GROUP-ID"):
                                source = media[i].get("NAME").split(" ")[0]
                                idx = i
                                break
                        else:
                            if quality in media[i].get("NAME"):
                                source = media[i].get("NAME").split(" ")[0]
                                idx = i
                                break

                    if (streamID and broadcastID not in streamID) or (not streamID and idx > -1): # Skip further parsing if current stream is equal to previous stream
                        streamURL = streamList.get("url")

                        if streamURL and streamURL[idx]:
                            playList = getAPIResponse(streamURL[idx], ignoreHeader=True, raw=True).decode("utf-8")

                            if playList and "#EXTM3U" in playList:
                                streamData = parseM3U8(playList, excludeURL=True, limit=7)

                                if streamData and isinstance(streamData, dict):
                                    sequence = streamData.get("#EXT-X-MEDIA-SEQUENCE")
                                    timeElapsed = streamData.get("#EXT-X-TWITCH-ELAPSED-SECS")
                                    timeTotal = streamData.get("#EXT-X-TWITCH-TOTAL-SECS")

                    try:
                        if serverTime and streamTime:
                            streamInfo["newStream"] = False if streamID and broadcastID in streamID else True
                            streamInfo["serverTime"] = float(serverTime)
                            streamInfo["streamTime"] = float(streamTime)
                            streamInfo["broadcastID"] = broadcastID
                            streamInfo["source"] = source

                            startTime = round(streamInfo["serverTime"] - streamInfo["streamTime"]) # Start time in nearest second
                            startTimeDT = datetime.fromtimestamp(startTime) # Local start time in datetime object
                            startTimeString = startTimeDT.strftime("[%y-%m-%d %I:%M:%S %p]") # Local start time in HH:MM:SS format

                            # Get elapsed time
                            elapsedTotal = datetime.now() - startTimeDT
                            elapsedTotal = time.strftime('%H:%M:%S', time.gmtime(elapsedTotal.total_seconds())) # Format into HH:MM:SS

                            streamInfo["startTimeString"] = startTimeString
                            streamInfo["elapsedTotal"] = elapsedTotal

                        if sequence and timeElapsed and timeTotal:
                            streamInfo["sequence"] = int(sequence)
                            streamInfo["timeElapsed"] = float(timeElapsed)
                            streamInfo["timeTotal"] = float(timeTotal)
                            streamInfo["startTime"] = startTime
                            streamInfo["needPartial"] = streamInfo["sequence"] > 0 or (streamInfo["timeTotal"] - streamInfo["timeElapsed"]) > 20.0
                    except:
                        pass

    # if streamInfo: safeprint(streamInfo)
    return streamInfo

class winNotify(threading.Thread):
    def __init__(self,  *args, **kwargs):
        super(winNotify, self).__init__(*args, **kwargs)
        try:
            self.displayName = kwargs.get("kwargs").get("displayName")
            self.loginID = kwargs.get("kwargs").get("loginID")
            self.elapsed = kwargs.get("kwargs").get("elapsed")
            self.title = kwargs.get("kwargs").get("title")
            self.game = kwargs.get("kwargs").get("game")
            self.url = "https://www.twitch.tv/{}".format(self.loginID)
        except:
            return

        self.stopThread = False
        self.daemon = True
        self.lastEvent = 0
        self.expiration = 3 * 60 * 1000 # Bug? Expiration isn't honored when compiled :(
        self.count = 0

        zroya.init("TLA", " ", " ", " ", TLAversion)
        self.template = zroya.Template(zroya.TemplateType.ImageAndText4)
        self.template.setFirstLine("생방알리미")
        self.template.setSecondLine("{} ({}) ({} 경과)".format(self.displayName, self.loginID, self.elapsed))
        self.template.setThirdLine(self.title)
        self.template.addAction("바로가기!")
        self.template.addAction("나중에...")

        if isfile(Logo):
            self.template.setImage(Logo)

        self.template.setExpiration(self.expiration)
        self.template.setAttribution(self.game)
        self.template.setAudio(audio=zroya.Audio.Alarm, mode=zroya.AudioMode.Default)

        self.start()

    def onClick(self, notification_id):
        self.stop()

    def onAction(self, notification_id, action_id):
        if action_id == 0:
            webbrowser.open(self.url)

        self.stop()

    def onDismiss(self, notification_id, reason):
        if reason == zroya.DismissReason.App:
            self.stop()
        elif reason == zroya.DismissReason.Expired:
            if self.lastEvent:
                if time.time() - self.lastEvent > 3:
                    self.count += 1
            else:
                self.lastEvent = time.time()
                self.count += 1
        elif reason == zroya.DismissReason.User:
            self.count += 1

    def onFail(self, notification_id):
        pass

    def run(self):
        try:
            nid = zroya.show(self.template, on_click=self.onClick, on_action=self.onAction, on_dismiss=self.onDismiss, on_fail=self.onFail)
            t0 = time.time()

            while True:
                if self.count > 1 or time.time() - t0 > (self.expiration / 1000) + 30:
                    self.stop()

                if self.stopThread:
                    zroya.hide(nid)
                    return True

                time.sleep(1)
        except Exception as e:
            safeprint("Notification Error: {}".format(e))

    def stop(self):
        self.stopThread = True

class ChannelLoopThread(threading.Thread):
    def __init__(self,  *args, **kwargs):
        global OAuthToken
        super(ChannelLoopThread, self).__init__(*args, **kwargs)
        self.stopThread = False
        self.daemon = True
        self.TWclientIDPriv = "\x6B\x69\x6D\x6E\x65\x37\x38\x6B\x78\x33\x6E\x63\x78\x36\x62\x72\x67\x6F\x34\x6D\x76\x36\x77\x6B\x69\x35\x68\x31\x6B\x6F"

        try:
            self.loginID = kwargs.get("name")
            self.userID = kwargs.get("kwargs").get("userID")
            self.displayName = kwargs.get("kwargs").get("displayName")
            self.sleep = kwargs.get("kwargs").get("sleep")
            self.newAlertsOnly = kwargs.get("kwargs").get("newAlertsOnly")
            self.notification = kwargs.get("kwargs").get("winnotify")
            self.TWclientID = kwargs.get("kwargs").get("TWclientID")
            self.botToken = kwargs.get("kwargs").get("botToken")
            self.TGclientID = kwargs.get("kwargs").get("TGclientID")
        except:
            return

        self.broadcastID = []

        if not self.sleep or self.sleep < 3: # Set default sleep value if not specified or set too low
            self.sleep = 10

        self.start()

    # Build and send message
    def buildMessage(self, streamInfo):
        # Skip messaging on first run if newAlertsOnly is set to true
        if self.newAlertsOnly:
            self.newAlertsOnly = False
            return

        if streamInfo:
            title = ""
            game = ""
            category = ""
            volt = u'\U000026A1'

            # Grab title and game
            url = "https://api.twitch.tv/kraken/channels/{0}".format(self.userID)
            info = getAPIResponse(url, clientID=self.TWclientID, kraken=True)

            if info and isinstance(info, dict) and not info.get("error"):
                title = info.get("status", "")

                if title is None: # Returns None for unset stream titles
                    title = ""

                title =  title.strip()
                game = info.get("game", "")

            if game:
                category = "<a href='https://www.twitch.tv/directory/game/{gameHTML}'>{game}</a>".format(gameHTML=quote(game, safe=''), game=escape(game))
            else:
                game = "-"
                category = "-"

            messagePrint = "{displayName} ({loginID}) {volt}\n" \
                            "시작: {start} ({elapsed} 경과)\n" \
                            "방제: '{title}'\n" \
                            "범주: '{game}'".format(displayName=self.displayName, loginID=self.loginID, volt=volt, start=streamInfo.get("startTimeString", ""), elapsed=streamInfo.get("elapsedTotal", ""), title=title, game=game)

            message = "<a href='https://www.twitch.tv/{loginID}'>{displayName} ({loginID})</a> {volt}\n" \
                        "시작: {start} (<i>{elapsed}</i> 경과)\n" \
                        "방제: <b>{title}</b>\n" \
                        "범주: {game}".format(displayName=self.displayName, loginID=self.loginID, volt=volt, start=streamInfo.get("startTimeString", ""), elapsed=streamInfo.get("elapsedTotal", ""), title=escape(title), game=category)

            safeprint("{0}\n{1} {2}\n{3}".format("-"*50, timeStamp(), messagePrint, "-"*50))

            if self.notification:
                winNotify(kwargs=dict(displayName=self.displayName, loginID=self.loginID, elapsed=streamInfo.get("elapsedTotal", ""), title=title, game=game))

            if not sendMessage(self.botToken, self.TGclientID, message):
                safeprint("{0} 텔레그램 메시지 전달이 딜레이 되거나 실패할 수 있읍니다...".format(timeStamp()))

    def run(self):
        while True:
            try:
                streamInfo = getStreamInformation(self.TWclientIDPriv, self.loginID, streamID=self.broadcastID)

                if streamInfo and isinstance(streamInfo, dict):
                    if streamInfo.get("newStream"):
                        if streamInfo.get("startTimeString"):
                            if len(self.broadcastID) > 4: # Keep last 5 broadcastIDs
                                self.broadcastID.pop(0)

                            self.broadcastID.append(streamInfo.get("broadcastID"))
                            self.buildMessage(streamInfo)
                        else: # Rare but sometimes time string isn't extracted
                            time.sleep(3)
                            continue

                if self.newAlertsOnly:
                    self.newAlertsOnly = False

                t0 = time.time()

                while time.time() - t0 < self.sleep:
                    if self.stopThread:
                        return True

                    time.sleep(1)
            except:
                pass

    def stop(self):
        self.stopThread = True

class TwitchLiveAlert:
    def __init__(self):
        safeprint("트위치 생방알리미 {0}".format(TLAversion))
        self.userData = {}
        self.priorityData = {}
        self.gameData = {}
        self.listHashP = 0
        self.listHashN = 0
        self.configFile = "알리미설정.ini"

        if self.createConfig(self.configFile): # Config file created
            exitOnKey()

        self.botToken = ""
        self.userListFile = "[일반] 알림목록.txt"
        self.userPriority = "[속성] 알림목록.txt"
        self.sendThumb = True
        self.refresh = 30
        self.refresh2 = 10
        self.newAlertsOnly = False
        self.notification = True
        self.loadConfig() # Read and load config
        self.initialAlert = self.newAlertsOnly

        clientIDSet = False

        if not self.botToken:
            safeprint("현기증 난단 말이에요. 빨리 '{0}' 파일에 토큰을 추가해 주세요".format(self.configFile))
            safeprint("'{0}' 파일을 열어 봇 토큰 설정 방법을 참고해 주세요".format(self.configFile))
            safeprint("토큰 설정이 안 된 경우 윈도우 알림 기능만 작동합니다")
            # exitOnKey()

        # Please use your own client id and secret
        self.TWclientID = "b36dxtency2u8jj09wx4tdqgwqk159"
        self.TWclientSecret = ""

        if not self.TGclientID: # Request TGclientID if missing from configFile
            self.TGclientID = getClientID(self.botToken)
        else:
            clientIDSet = True # TGclientID is set from configFile

        if not self.TGclientID: # Exit if failed to fetch TGclientID
            safeprint("클라이언트 아이디 정보가 없습니다. 토큰설정이 잘 못 되었거나 봇에게 먼저 말을 걸어주세요")
            # safeprint("Unable to fetch client ID. Please make sure bot token is correct or send any message to bot if running for the first time.")
            # exitOnKey()
        else:
            if not clientIDSet:
                safeprint("[클라이언트 아이디]: {0}".format(self.TGclientID))

        safeprint("\n[속성] | [목록파일: '{0}'] [갱신대기 {1}초]".format(self.userPriority, self.refresh2))
        safeprint("[일반] | [목록파일: '{0}'] [갱신대기 {1}초] [썸네일 {2}]\n".format(self.userListFile, self.refresh, "ON" if self.sendThumb else "OFF"))

    # Create missing config file
    def createConfig(self, fileName):
        if not isfile(fileName): # config file missing
            configString = \
                        "; 생방알리미 (Twitch Live Alert) 설정 파일\n" \
                        "\n" \
                        "; 텔레그램 봇 생성 및 토큰 얻기 https://telegram.me/botfather\n" \
                        "; 참고 이미지 링크: https://i.imgur.com/soxLdbJ.jpg\n" \
                        "; 텔레그램에서 BotFather를 검색하고 /start 와 /newbot 명령어를 입력해 봇을 만들어 줍니다\n" \
                        "; 봇 이름과 봇 계정이름을 입력 해줍니다 (여기서 봇 계정이름의 끝은 bot으로 끝나야 합니다)\n" \
                        "; 봇 계정 설정이 끝나면 토큰 값을 보내주는데 이 값을 복사해서 아래 token 항목에 붙여넣습니다\n" \
                        "; **중요: 그리고 본인이 새로 만든 봇을 검색해서 먼저 아무 말이나 대화를 걸어 줘야합니다\n" \
                        "\n" \
                        "; <token>\n" \
                        "; 텔레그램 봇을 만들면 아래와 같은 형식의 토큰을 생성해줍니다. 토큰을 받아서 설정해 줍니다\n" \
                        "; token = 110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw\n" \
                        "\n" \
                        "; <clientid> 텔레그램 클라이언트 아이디\n" \
                        "; 필수 사항은 아니며 설정하지 않은 경우 프로그램 실행시 자동으로 받아옵니다\n" \
                        "; 가끔씩 봇에게 말을 다시 걸어줘야 정상 작동하는 경우가 있는데 클라이언트 아이디를 직접 설정해주면 그런 현상이 사라집니다\n" \
                        "; 본인의 클라이언트 아이디는 프로그램을 실행하면 아래와 같은 메시지를 콘솔 창으로 확인할 수 있읍니다\n" \
                        "; '설정파일 로딩 완료!'\n" \
                        "; '[클라이언트 아이디]: 12345678'\n" \
                        "; clientid = 12345678\n" \
                        "\n" \
                        "; <userlist> 일반 알리미 유저 목록 파일\n" \
                        "; 해당 파일에 알림을 받을 스트리머의 로그인 아이디를 한줄에 한명씩 추가합니다\n" \
                        "; 이 목록은 실시간으로 수정이 반영되므로 프로그램 실행중 언제든지 추가 및 삭제가 가능합니다\n" \
                        "; userlist = [일반] 알림목록.txt\n" \
                        "; 알리미 실행 파일과 위치가 다른 경우 파일 전체 경로를 설정해주세요\n" \
                        "; userlist = C:\\Users\\cooluser\\Desktop\\직박구리\\레전드.txt\n" \
                        "\n" \
                        "; <userpriority> 속성 알리미 유저 목록 파일\n" \
                        "; 해당 파일에 알림을 받을 스트리머의 로그인 아이디를 한줄에 한명씩 추가합니다\n" \
                        "; 이 목록은 실시간으로 수정이 반영되므로 프로그램 실행중 언제든지 추가 및 삭제가 가능합니다\n" \
                        "; userpriority = [속성] 알림목록.txt\n" \
                        "; 알리미 실행 파일과 위치가 다른 경우 파일 전체 경로를 설정해주세요\n" \
                        "; userpriority = C:\\Users\\cooluser\\Desktop\\찌르레기\\전설.txt\n" \
                        "\n" \
                        "; <sendthumbnail> 썸네일 사용 여부\n" \
                        "; 텔레그램 알림 메시지에 썸네일을 포함합니다. 속성 알림은 썸네일을 지원하지 않습니다\n" \
                        "; 썸네일을 포함한 메시지를 전송합니다 (썸네일 평균 용량은 20-40kb 정도입니다)\n" \
                        "; sendthumbnail = True\n" \
                        "; 썸네일 없이 메시지만 전송합니다\n" \
                        "; sendthumbnail = False\n" \
                        "\n" \
                        "; <refreshdelay> 일반 목록 갱신 대기 시간(초)\n" \
                        "; 트위치 API를 통해 생방송 여부를 확인하고 다음 확인때까지 대기시간입니다\n" \
                        "; 빠르게 재요청해도 서버에서 정보 업데이트를 바로 안 해주기 때문에 20~60초 사이의 딜레이를 권장합니다\n" \
                        "; refreshdelay = 30\n" \
                        "\n" \
                        "; <refreshpriority> 속성 목록 갱신 대기 시간(초)\n" \
                        "; 비공식 API를 통해 생방송 여부를 개별적으로 확인하고 다음 확인때까지 대기시간입니다\n" \
                        "; 서버에 부담을 줄이기 위해 일반적으로 5~20초 (최소 3) 사이의 딜레이를 권장합니다\n" \
                        "; refreshpriority = 10\n" \
                        "\n" \
                        "; <newalertsonly> 프로그램 시작시 진행중인 방송 알림 여부\n" \
                        "; 프로그램 실행 후 새로운 방송만 알림을 받습니다\n" \
                        "; newalertsonly = True\n" \
                        "; 프로그램 실행 후 현재 진행중인 방송도 알림을 받습니다\n" \
                        "; newalertsonly = False\n" \
                        "\n" \
                        "; <winnotify> 방송 시작시 윈도우 알림 여부 (윈8 이상만 지원)\n" \
                        "; 방송 시작시 윈도우 알림을 받습니다\n" \
                        "; winnotify = True\n" \
                        "; 윈도우 알림을 받지 않습니다\n" \
                        "; winnotify = False\n" \
                        "\n"

            safeprint("설정파일 생성중 ...")
            config = configparser.ConfigParser()

            # Default output
            config["LiveAlertConfig"] = {
                "token": "",
                "clientid": "",
                "userlist": "[일반] 알림목록.txt",
                "userpriority": "[속성] 알림목록.txt",
                "sendthumbnail": "True",
                "refreshdelay": "30",
                "refreshpriority": "10",
                "newalertsonly": "True",
                "winnotify": "True"
            }

            with open(fileName, 'w', encoding="utf-8") as configfile:
                configfile.write(configString)
                config.write(configfile)
                safeprint("'{0}' 파일을 열어 먼저 설정해주세요".format(fileName))

            return True

    # Read and load config
    def loadConfig(self):
        config = configparser.ConfigParser()

        try:
            config.read(self.configFile, encoding="utf_8_sig")

            if 'LiveAlertConfig' in config:
                self.botToken = config["LiveAlertConfig"].get("token", "")
                self.TGclientID = config["LiveAlertConfig"].get("clientid", "")
                self.userListFile = config["LiveAlertConfig"].get("userlist", "[일반] 알림목록.txt")
                self.userPriority = config["LiveAlertConfig"].get("userpriority", "[속성] 알림목록.txt")
                self.sendThumb = config["LiveAlertConfig"].getboolean("sendthumbnail", True)
                self.refresh = int(config["LiveAlertConfig"].get("refreshdelay", 30))
                self.refresh2 = int(config["LiveAlertConfig"].get("refreshpriority", 10))
                self.newAlertsOnly = config["LiveAlertConfig"].getboolean("newalertsonly", False)
                self.notification = config["LiveAlertConfig"].getboolean("winnotify", True)
                safeprint("설정파일 로딩 완료!")
        except Exception as e:
            safeprint("Error: {}".format(e))

    # Get userData from list of loginIDs using Helix API
    def getUserDatafromLoginIDs(self, loginIDList, kraken=None):
        maxURLSize = 99
        lowerIndex = 0
        userData = {}

        if loginIDList:
            while lowerIndex < len(loginIDList): # Loop through loginIDList and update streamData information
                if kraken:
                    url = "https://api.twitch.tv/kraken/users?"
                else:
                    url = "https://api.twitch.tv/helix/users?"

                upperIndex = min(lowerIndex + maxURLSize, len(loginIDList))

                for k in loginIDList[lowerIndex:upperIndex]:
                    if kraken:
                        url += "login=" + k + ","
                    else:
                        url += "login=" + k + "&"

                if url[-1] == "&" or url[-1] == ",":
                    url = url[:-1]

                lowerIndex += maxURLSize
                info = getAPIResponse(url, clientID=self.TWclientID, token=OAuthToken, kraken=kraken)

                if info:
                    if kraken:
                        if info.get("users"):
                            for n in info.get("users"):
                                userData[n.get("name")] = [n.get("_id"), n.get("display_name"), [n.get("streamID")] if n.get("streamID") else []]
                    else:
                        for n in info["data"]:
                            userData[n.get("login")] = [n.get("id"), n.get("display_name"), [n.get("streamID")] if n.get("streamID") else []] # loginID: [userID, displayName, streamID]

        return userData

    # Request UserData API if missing key value pair
    def needUpdate(self, loginIDList, userData):
        for n in loginIDList:
            if n not in userData:
                return True

        return False

    # Add or remove loginID from userData
    def updateUserData(self, userData, forced=None, priority=None):
        loginIDList = []
        removed = []
        added = []
        dataResponse = {}

        if priority:
            loginIDList = fileToList(self.userPriority, removeDuplicate=True)
            userHash = self.listHashP
        else:
            loginIDList = fileToList(self.userListFile, removeDuplicate=True)
            userHash = self.listHashN

        # Remove non-matching key
        for k in list(userData):
            if k not in loginIDList:
                userData.pop(k, None)
                removed.append(str(k))

        currentHash = hash(str(loginIDList)) # Get list hash

        if (currentHash != userHash and self.needUpdate(loginIDList, userData)) or forced: # Update when hash changes or when forced
            if priority:
                self.listHashP = currentHash
            else:
                self.listHashN = currentHash

            dataResponse = self.getUserDatafromLoginIDs(loginIDList)

            if dataResponse:
                # Add missing key value pair
                for k, v in dataResponse.items():
                    if k not in userData:
                        userData.update({k:v})
                        added.append(str(k))

                # Remove invalid key value pair from userData (either username has changed or banned)
                for k in list(userData):
                    if k not in dataResponse:
                        userData.pop(k, None)
                        removed.append(str(k))

        listType = "[속성] " if priority else "[일반] "

        if added or removed:
            safeprint("{0} {1}알리미 목록이 업데이트 되었읍니다 [{2}]".format(timeStamp(), listType, len(userData)))

            if removed:
                safeprint("{0} {1}목록에서 {2} 명을 삭제했읍니다\n{3}\n".format(timeStamp(), listType, len(removed), removed))
            if added:
                safeprint("{0} {1}목록에 {2} 명을 추가했읍니다\n{3}\n".format(timeStamp(), listType, len(added), added))

            missing = [n for n in loginIDList if n not in userData]

            if missing:
                safeprint("{0} 아래 {1}목록의 아이디를 조회할 수 없읍니다. 다시 확인해주세요\n{2}".format(timeStamp(), listType, missing))

        return userData

    # Search for matching element in list value from dictionary and returns corresponding key
    def searchForValue(self, dict, searchFor):
        for k, v in dict.items():
            if isinstance(v, list) and searchFor in v:
                return k

        return None

    # Build gameID to gameName dictionary
    def getGameResponse(self, streamData):
        if not streamData:
            return False

        gameIDs = list(n[4] for n in streamData.values() if n[4] not in self.gameData) # List of gameIDs
        gameIDs = list(set(gameIDs)) # Remove duplicates, no order preserved

        if gameIDs:
            # safeprint("Found new gameIDs: {0}".format(gameIDs))
            maxURLSize = 99
            lowerIndex = 0

            while lowerIndex < len(gameIDs):
                url = "https://api.twitch.tv/helix/games?"
                upperIndex = min(lowerIndex + maxURLSize, len(gameIDs))

                for k in gameIDs[lowerIndex:upperIndex]:
                    url += "id=" + k + "&"

                if url[-1] == "&":
                    url = url[:-1]

                lowerIndex += maxURLSize

                info = getAPIResponse(url, clientID=self.TWclientID, token=OAuthToken)

                if info:
                    for n in info["data"]:
                        if n.get("id") not in self.gameData:
                            self.gameData[n.get("id")] = n.get("name")

        # safeprint("Updated gameData: {0}".format(self.gameData))

    # Returns updated streamData in the form { userID: [displayName, streamTitle, timeStamp, viewerCount, gameID], ... }
    def getLiveResponse(self):
        loginIDList = list(self.userData.keys())

        maxURLSize = 99
        lowerIndex = 0
        streamData = {}

        while lowerIndex < len(loginIDList): # Loop through loginIDList and update streamData information
            url = "https://api.twitch.tv/helix/streams?"
            upperIndex = min(lowerIndex + maxURLSize, len(loginIDList))

            for k in loginIDList[lowerIndex:upperIndex]:
                url += "user_login=" + k + "&"

            if url[-1] == "&":
                url = url[:-1]

            lowerIndex += maxURLSize

            info = getAPIResponse(url, clientID=self.TWclientID, token=OAuthToken)

            if info:
                for n in info["data"]:
                    match = self.searchForValue(self.userData, n.get("user_id"))

                    if match:
                        streamID = n.get("id")

                        if streamID and streamID not in self.userData.get(match)[2]: # New streamID
                            if len(self.userData.get(match)[2]) > 4: # Keep last 5 streamIDs
                                self.userData.get(match)[2].pop(0)

                            self.userData.get(match)[2].append(streamID)
                            streamData[match] = [n.get("user_name"), n.get("title"), n.get("started_at"), n.get("viewer_count"), n.get("game_id")]

        # Build gameID to gameName dictionary
        if streamData:
            self.getGameResponse(streamData)

        return streamData

    # Build and send message
    def buildMessage(self, streamData, sendThumb=True):
        # Skip messaging on first run if newAlertsOnly is set to true
        if self.newAlertsOnly:
            self.newAlertsOnly = False
            return

        if streamData:
            eye = u'\U0001F441'

            for n in streamData:
                timeStr = convertUTCtoLocalTime(streamData.get(n)[2])
                thumbURL = "https://static-cdn.jtvnw.net/previews-ttv/live_user_{0}-640x360.jpg?a={1}".format(n, time.time())
                category = self.gameData.get(streamData.get(n)[4], "")

                if category:
                    category = "<a href='https://www.twitch.tv/directory/game/{gameHTML}'>{game}</a>".format(gameHTML=quote(category, safe=''), game=escape(category))
                else:
                    category = "-"

                messagePrint = "{0} ({loginID}) ({view} 명 시청중)\n" \
                                "시작: {2} ({3} 경과)\n" \
                                "방제: '{1}'\n" \
                                "범주: '{game}'".format(streamData.get(n)[0], streamData.get(n)[1].strip(), timeStr[0], timeStr[1], loginID=n, view=streamData.get(n)[3], game=self.gameData.get(streamData.get(n)[4], "-"))

                message = "<a href='https://www.twitch.tv/{loginID}'>{0} ({loginID})</a> ({eye} <i>{view}</i>)\n" \
                            "시작: {2} (<i>{3}</i> 경과)\n" \
                            "방제: <b>{1}</b>\n" \
                            "범주: {game}".format(streamData.get(n)[0], escape(streamData.get(n)[1].strip()), timeStr[0], timeStr[1], loginID=n, eye=eye, view=streamData.get(n)[3], game=category)

                safeprint("{0}\n{1} {2}\n{3}".format("-"*50, timeStamp(), messagePrint, "-"*50))

                if self.notification:
                    winNotify(kwargs=dict(displayName=streamData.get(n)[0], loginID=n, elapsed=timeStr[1], title=streamData.get(n)[1].strip(), game=self.gameData.get(streamData.get(n)[4], "-")))

                rval = False

                if sendThumb:
                    rval = sendPhoto(self.botToken, self.TGclientID, thumbURL, message)
                else:
                    rval = sendMessage(self.botToken, self.TGclientID, message)

                if not rval:
                    safeprint("{0} 텔레그램 메시지 전달이 딜레이 되거나 실패할 수 있읍니다...".format(timeStamp()))

                time.sleep(2) # Give some delay between consecutive alerts

    def createAlertFile(self, fileName):
        if not isfile(fileName):
            safeprint("'{0}' 알림 목록 파일이 존재하지 않아 생성합니다 ...".format(fileName))

            try:
                # Create directories if missing
                directory = dirname(fileName)

                if directory and not exists(directory):
                    makedirs(directory)

                open(fileName, "w").close() # Create file
                safeprint("'{0}' 파일을 열어 스트리머의 로그인 아이디를 한줄에 한명씩 추가해 주세요".format(fileName))
                safeprint("이 목록은 실시간으로 수정이 반영됩니다\n")
            except OSError as e:
                safeprint("Error: " + str(e))
                safeprint("'{0}' 파일 생성에 실패했읍니다. 파일 경로를 다시 확인해 주세요".format(fileName))
                exitOnKey()

    # Main loop thread
    def loopLiveAlert(self, fileName="[일반] 알림목록.txt", fileName2="[속성] 알림목록.txt"):
        global needOAuthUpdate
        global OAuthToken

        forceCount = 0
        forceUpdate = False
        self.createAlertFile(fileName)
        self.createAlertFile(fileName2)

        stopwatch = u'\U000023F1'
        safeprint(timeStamp(), "트위치 생방알리미 시작!")
        sendMessage(self.botToken, self.TGclientID, "{0} 트위치 생방알리미 시작!\n[일반] | [썸네일 <i>{1}</i>] [{stopwatch} <i>{2}</i>초]\n[속성] | [{stopwatch} <i>{3}</i>초]".format(timeStamp(), "ON" if self.sendThumb else "OFF", self.refresh, self.refresh2, stopwatch=stopwatch))

        if not validateOAuthToken(self.TWclientID):
            # safeprint("{} Need to get valid OAuth Token".format(timeStamp()))
            safeprint("{} 유효한 인증 토큰이 필요합니다".format(timeStamp()))
            getOAuthToken(self.TWclientID, self.TWclientSecret)

        OAuthToken = setOAuthToken(self.TWclientID)

        while True:
            if needOAuthUpdate:
                safeprint("{} Need to update OAuth Token...".format(timeStamp()))
                needOAuthUpdate = False
                getOAuthToken(self.TWclientID, self.TWclientSecret)
                OAuthToken = setOAuthToken(self.TWclientID)

            if forceCount > 5:
                forceUpdate = True
                forceCount = 0

            # Update priorityData
            self.priorityData = self.updateUserData(self.priorityData, forced=forceUpdate, priority=True)

            # Stop threads that are no longer in priority list
            for t in threading.enumerate():
                if t.name != "MainThread" and t.name not in list(self.priorityData.keys()):
                    t.stop()

            if self.priorityData: # loginID: [userID, displayName, streamID]
                currentThreads = [t.name for t in threading.enumerate() if t.name != "MainThread"]

                for n in self.priorityData:
                    if n not in currentThreads: # Start missing thread
                        userInfo = self.priorityData.get(n)

                        if userInfo:
                            ChannelLoopThread(name=n, kwargs=dict(userID=userInfo[0], displayName=userInfo[1], sleep=self.refresh2, newAlertsOnly=self.initialAlert, winnotify=self.notification, TWclientID=self.TWclientID, botToken=self.botToken, TGclientID=self.TGclientID))

            # Update userData
            self.userData = self.updateUserData(self.userData, forced=forceUpdate, priority=False)

            if self.userData:
                streamData = self.getLiveResponse()
                self.buildMessage(streamData, self.sendThumb)

            if forceUpdate:
                forceUpdate = False

            forceCount += 1
            time.sleep(self.refresh)

def main():
    try:
        signal.signal(signal.SIGINT, signalHandler)
        liveAlert = TwitchLiveAlert()
        liveAlert.loopLiveAlert(liveAlert.userListFile, liveAlert.userPriority)
    except Exception:
        safeprint("{} Main thread error!".format(timeStamp()))
        traceback.print_exc()
        msvcrt.getch()

if __name__ == "__main__":
    setpriority()
    TLAversion = "v2.3"
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning) # Suppress warning messages
    needOAuthUpdate = False
    OAuthToken = ""
    printLock = threading.Lock()
    Logo = resourcePath("bt.ico")
    CACert = resourcePath("certifi/cacert.pem")
    baseLib = resourcePath("base_library.zip")

    # Lock files
    if getattr(sys, 'frozen', False): # Only when run in bundle
        os.open(Logo, os.O_RDONLY)
        os.open(CACert, os.O_RDONLY)
        os.open(baseLib, os.O_RDONLY)

    main()
