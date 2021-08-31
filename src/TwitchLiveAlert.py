#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, signal
import win32api,win32process,win32con
import configparser
import msvcrt
import os
from os import makedirs
from os.path import isfile, join, exists, dirname, abspath, basename, splitext
import requests
import json
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import time
from datetime import datetime, timedelta
from html import escape
from urllib.parse import quote
import hashlib
import threading
import re
import traceback
import logging

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# Thread safe print
def safeprint(*args, **kwargs):
    with printLock:
        if logConsole:
            logging.info(*args, **kwargs)
        else:
            print(*args, **kwargs)

# Handle system interrupt to break python loop scope
def signalHandler(signal, frame):
    threads = [t for t in threading.enumerate() if t.name != "MainThread"]

    if threads:
        safeprint("\nKeyboard interrupt: Stopping {0} thread{1} before main thread...".format(len(threads), "s" if len(threads) != 1 else ""))

        for t in threads:
            t.stop()
        for t in threads:
            t.join()

    sys.exit()

# Keyboard event
def kbFunc():
    return ord(msvcrt.getch()) if msvcrt.kbhit() else 0

# Pause and exit on key press
def exitOnKey():
    safeprint("아무 키나 누르면 종료 된다에요...")
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
    filePath = join(appPath, "oauth_{}".format(clientID))

    url = "https://id.twitch.tv/oauth2/token?client_id={0}&client_secret={1}&grant_type=client_credentials".format(clientID, clientSecret)

    response = getAPIResponse(url, kraken=True, ignoreHeader=True, post=True)

    try:
        # safeprint("{} Fetching new access token...".format(timeStamp()))
        safeprint("{} 새로운 토큰을 발급 받는 중...".format(timeStamp()))

        if response:
            if response.get("status"):
                safeprint("{} Error: {} - {}".format(timeStamp(), response.get("status"), response.get("message")))
            elif response.get("access_token"):
                data = json.dumps(response)
                outputFile(filePath, data, mode="w", raw=True)
                # safeprint("{} Successfully grabbed access token!".format(timeStamp()))
                safeprint("{} 성공적으로 새로운 토큰을 받았다에요!".format(timeStamp()))
    except:
        pass

# Returns True if current OAuth token is valid
def validateOAuthToken(clientID):
    filePath = join(appPath, "oauth_{}".format(clientID))

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
    filePath = join(appPath, "oauth_{}".format(clientID))

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
        return {}

    clientIDs = {}
    url = "https://api.telegram.org/bot{0}/{1}".format(botToken, "getUpdates")

    res = getAPIResponse(url, kraken=True, ignoreHeader=True)

    if res:
        try:
            if res.get("ok") and res.get("result"):
                for r in res.get("result"):
                    if r.get("message"): # User
                        # name = r.get("message").get("from").get("first_name")
                        name = "기본"
                        id = r.get("message").get("from").get("id")

                        if id == r.get("message").get("chat").get("id"):
                            if id and name not in clientIDs:
                                clientIDs.update({name:id})
                    elif r.get("channel_post"): # Channel
                        name = r.get("channel_post").get("sender_chat").get("title")
                        id = r.get("channel_post").get("sender_chat").get("id")

                        if id and name not in clientIDs:
                            clientIDs.update({name:id})
                    elif r.get("my_chat_member"): # Group
                        name = r.get("my_chat_member").get("chat").get("title")
                        id = r.get("my_chat_member").get("chat").get("id")

                        if id and name not in clientIDs:
                            clientIDs.update({name:id})

        except:
            # if res.get("ok"):
                # safeprint("{} Error fetching Telegram clientID. Please initiate a conversation first.".format(timeStamp()))
            # else:
                # safeprint("{} Error fetching Telegram clientID: {} - {}".format(timeStamp(), res.get("error_code", ""), res.get("description", "")))
            pass

    return clientIDs

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
                safeprint("메시지 전달 오류: 설정 파일이 잘 못 되었거나 메시지 호환이 안 된다에요")
            elif res["error_code"] == 403:
                safeprint("메시지 권한 오류: 봇에게 먼저 대화를 걸어 주세요")
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
                safeprint("메시지 전달 오류: 설정 파일이 잘 못 되었거나 메시지 호환이 안 된다에요")
            elif res["error_code"] == 403:
                safeprint("메시지 권한 오류: 봇에게 먼저 대화를 걸어 주세요")
            else:
                if res.get("error_code"):
                    safeprint("메시지 오류: {}".format(res.get("error_code")))
        else:
            return True

    return False

# Convert time from UTC to local
def convertUTCtoLocalTime(timeStr, format="[%y-%m-%d %I:%M:%S %p]", localTimeZone=""):
    startTime = ""
    elapsed = None

    try:
        if timeStr:
            if timeStr[-1].lower() == "z": # Strip Z at the end of string
                timeStr = timeStr[:-1]

            startTime = datetime.fromisoformat(timeStr).replace(tzinfo=ZoneInfo("Etc/UTC")) # Convert to UTC time object
            currentTime = datetime.now().astimezone()

            # Convert to spcecified timezone or local start time
            if localTimeZone:
                startTime = startTime.astimezone(ZoneInfo(localTimeZone))
            else:
                startTime += currentTime.utcoffset()
                startTime = startTime.replace(tzinfo=None).astimezone()

            # Get elapsed time
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
        safeprint("Error: {}".format(str(e)))

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
        safeprint("Error: {}".format(str(e)))

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
def getStreamInformation(clientID, loginID, quality="best", streamID=[], localTimeZone=""):
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
                            currentTime = datetime.now().astimezone()
                            startTimeDT = datetime.utcfromtimestamp(startTime).replace(tzinfo=ZoneInfo("Etc/UTC")) # Convert to UTC time object

                            # Convert to spcecified timezone or local start time
                            if localTimeZone:
                                startTimeDT = startTimeDT.astimezone(ZoneInfo(localTimeZone))
                            else:
                                startTimeDT += currentTime.utcoffset()
                                startTimeDT = startTimeDT.replace(tzinfo=None).astimezone()

                            startTimeString = startTimeDT.strftime("[%y-%m-%d %I:%M:%S %p]") # Local start time in HH:MM:SS format

                            # Get elapsed time
                            elapsedTotal = currentTime - startTimeDT
                            elapsedTotal = time.strftime('%H:%M:%S', time.gmtime(elapsedTotal.total_seconds())) # Format into HH:MM:SS

                            streamInfo["startTime"] = startTime
                            streamInfo["startTimeString"] = startTimeString
                            streamInfo["elapsedTotal"] = elapsedTotal

                        if sequence and timeElapsed and timeTotal:
                            streamInfo["sequence"] = int(sequence)
                            streamInfo["timeElapsed"] = float(timeElapsed)
                            streamInfo["timeTotal"] = float(timeTotal)
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
            self.startTime = kwargs.get("kwargs").get("startTime")
            self.elapsed = kwargs.get("kwargs").get("elapsed")
            self.title = kwargs.get("kwargs").get("title")
            self.game = kwargs.get("kwargs").get("game")
            self.oldName = kwargs.get("kwargs").get("oldName")
            self.btype = kwargs.get("kwargs").get("btype")
            self.oldID = kwargs.get("kwargs").get("oldID")
            self.url = "https://www.twitch.tv/{}".format(self.loginID)
        except:
            return

        self.logo = Logo
        self.daemon = True
        self.changed = False
        self.types = ["일반", "제휴", "파트너"]
        self.arrow = u'\U0001F846'

        self.createShellLink(appName, AUMID)

        if self.btype:
            self.generateTemplate(
                text1="{} ({})".format(self.displayName, self.loginID),
                text2="[{}] {} [{}] 회원이 되었어요{}".format(self.types[int(self.btype[0])], self.arrow, self.types[int(self.btype[1])], ("..." if int(self.btype[0]) - int(self.btype[1]) > 0 else "!")),
                attribution="{}".format("강등 되었다에요..ㅠㅠ" if int(self.btype[0]) - int(self.btype[1]) > 0 else "구독 '해줘'"))
        else:
            if self.oldName:
                self.generateTemplate(
                    text1="{} ({})".format(self.displayName, self.loginID),
                    text2="[{}] {} [{}]".format(self.oldName, self.arrow, self.displayName),
                    text3="닉네임이 변경 되었어요!".format(),
                    attribution="{}".format("이건 굉장히 귀하네요"))
            elif self.oldID:
                self.generateTemplate(
                    text1="{} ({})".format(self.displayName, self.loginID),
                    text2="[{}] {} [{}]".format(self.oldID, self.arrow, self.loginID),
                    text3="아이디가 변경 되었어요!".format(),
                    attribution="{}".format("알림 목록 파일을 수정해 주세요"))
            else:
                self.generateTemplate(
                    text1="{} ({}) ({} 경과)".format(self.displayName, self.loginID, self.elapsed),
                    text2="시작: {}".format(self.startTime),
                    text3="{}".format(self.title),
                    attribution="{}".format(self.game))

        if self.changed: # Wait for update
            self.changed = False
            time.sleep(4)

        self.start()

    def generateTemplate(self, template="ToastGeneric", text1="", text2="", text3="", attribution=""):
        self.tString = """
            <toast>
            <visual>
                <binding template="{template}">
                    <image placement="appLogoOverride" src="{logo}" />
                    <text>{text1}</text>
                    <text>{text2}</text>
                    <text>{text3}</text>
                    <text placement="attribution">{attribution}</text>
                </binding>
            </visual>
            <actions>
                <action content="바로가기!" activationType="protocol" arguments="{url}" />
                <action content="나중에..." activationType="system" arguments="dismiss" />
            </actions>
            <audio src="ms-winsoundevent:Notification.Looping.Alarm" />
            </toast>
        """

        self.tString = self.tString.format(logo=self.logo, template=template, text1=escape(text1), text2=escape(text2), text3=escape(text3), attribution=escape(attribution), url=self.url)

    def createShellLink(self, appName, AUMID):
        import pythoncom
        from win32com.shell import shell, shellcon
        from win32com.propsys import propsys, pscon
        import win32timezone

        # Create shortcut
        shortcutPath = r"C:\Users\{}\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\{}.lnk".format(os.getenv('username'), appName)
        targetPath = os.path.abspath(sys.executable)

        shortcutInstance = pythoncom.CoCreateInstance(shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink)
        persistFile = shortcutInstance.QueryInterface(pythoncom.IID_IPersistFile)

        if isfile(shortcutPath):
            persistFile.Load(shortcutPath)
            currentTarget, _ = shortcutInstance.GetPath(shell.SLGP_RAWPATH)
            currentDir = shortcutInstance.GetWorkingDirectory()

            if currentTarget != targetPath or currentDir != appPath:
                shortcutInstance.SetPath(targetPath)
                shortcutInstance.SetWorkingDirectory(appPath)
                persistFile.Save(shortcutPath, 0)
        else:
            shortcutInstance.SetPath(targetPath)
            shortcutInstance.SetWorkingDirectory(appPath)
            persistFile.Save(shortcutPath, 0)

        # Get AUMID value
        store = propsys.SHGetPropertyStoreFromParsingName(shortcutPath, None, shellcon.GPS_READWRITE, propsys.IID_IPropertyStore)
        currentID = store.GetValue(pscon.PKEY_AppUserModel_ID).GetValue()

        # Set AUMID value
        if (currentID != AUMID):
            store.SetValue(pscon.PKEY_AppUserModel_ID, propsys.PROPVARIANTType(AUMID, pythoncom.VT_LPWSTR))
            store.Commit()
            self.changed = True

    def run(self):
        import winrt.windows.data.xml.dom as dom
        from winrt.windows.ui.notifications import ToastNotificationManager, ToastNotification

        if not self.displayName: # Init only
            return

        try:
            # Convert to XmlDocument
            self.xDoc = dom.XmlDocument()
            self.xDoc.load_xml(self.tString)

            # Create notifier
            self.notifier = ToastNotificationManager.create_toast_notifier(AUMID)
            self.notifier.show(ToastNotification(self.xDoc))
        except Exception as e:
            safeprint("Notification Error: {}".format(e))

class ChannelLoopThread(threading.Thread):
    def __init__(self,  *args, **kwargs):
        global OAuthToken
        super(ChannelLoopThread, self).__init__(*args, **kwargs)
        self.stopThread = False
        self.daemon = True
        self.TWclientIDPriv = ""

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
            self.localTimeZone = kwargs.get("kwargs").get("localTimeZone")
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
            ts = streamInfo.get("startTime", "")
            hashStr1 = "{}_{}_{}".format(self.loginID, streamInfo.get("broadcastID", ""), ts)
            hashStr2 = "{}_{}_{}".format(self.loginID, streamInfo.get("broadcastID", ""), int(ts) + 1 if ts else "") 
            hashSha1 = []
            hashSha1.append(hashlib.sha1(hashStr1.encode()).hexdigest()[:20])
            hashSha1.append(hashlib.sha1(hashStr2.encode()).hexdigest()[:20])

            # Grab title and game
            url = "https://api.twitch.tv/helix/channels?broadcaster_id={0}".format(self.userID)
            info = getAPIResponse(url, clientID=self.TWclientID, token=OAuthToken)

            if info and isinstance(info, dict):
                for n in info.get("data"):
                    title = n.get("title", "")
                    title = title.strip()
                    game = n.get("game_name", "")

            if game:
                category = "<a href='https://www.twitch.tv/directory/game/{gameHTML}'>{game}</a>".format(gameHTML=quote(game, safe=''), game=escape(game))
            else:
                game = "-"
                category = "-"

            messagePrint = "{} ({}) {}\n".format(self.displayName, self.loginID, volt) + \
                            "시작: {} ({} 경과)\n".format(streamInfo.get("startTimeString", ""), streamInfo.get("elapsedTotal", "")) + \
                            "방제: '{}'\n".format(title) + \
                            "범주: '{}'\n".format(game) + \
                            "\n{}_{}\n{}_{}".format(hashSha1[0], hashStr1, hashSha1[1], hashStr2)

            message = "<a href='https://www.twitch.tv/{loginID}'>{displayName} ({loginID})</a> {volt}\n".format(loginID=self.loginID, displayName=self.displayName, volt=volt) + \
                        "시작: {} (<i>{}</i> 경과)\n".format(streamInfo.get("startTimeString", ""), streamInfo.get("elapsedTotal", "")) + \
                        "방제: <b>{}</b>\n".format(escape(title)) + \
                        "범주: {}".format(category)

            safeprint("{0}\n{1} {2}\n{3}".format("-"*50, timeStamp(), messagePrint, "-"*50))

            if self.notification:
                winNotify(kwargs=dict(displayName=self.displayName, loginID=self.loginID, startTime=streamInfo.get("startTimeString", ""), elapsed=streamInfo.get("elapsedTotal", ""), title=title, game=game))

            if not sendMessage(self.botToken, self.TGclientID, message):
                safeprint("{0} 텔레그램 메시지 전달이 늦거나 실패할 수 있다에요...".format(timeStamp()))

    def run(self):
        while True:
            try:
                streamInfo = getStreamInformation(self.TWclientIDPriv, self.loginID, streamID=self.broadcastID, localTimeZone=self.localTimeZone)

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
        safeprint("{}\n트위치 {} {}\n{}".format("-"*50, appName, TLAversion, "-"*50))
        self.userData = {}
        self.priorityData = {}
        self.changeData = []
        self.changedID = [[], []]
        self.gameData = {}
        self.listHashP = 0
        self.listHashN = 0
        self.runOnStart = True

        if self.createConfig(configFile): # Config file created
            exitOnKey()

        self.botToken = ""
        self.userListFile = "[일반] 알림목록.txt"
        self.userPriority = "[속성] 알림목록.txt"
        self.sendThumb = True
        self.refresh = 30
        self.refresh2 = 10
        self.newAlertsOnly = False
        self.alertChange = True
        self.notification = True
        self.silentstart = False
        self.localTimeZone = ""
        self.loadConfig() # Read and load config
        self.initialAlert = self.newAlertsOnly

        clientIDSet = False

        if not self.botToken:
            safeprint("현기증 난단 말이에요. 빨리 '{0}' 파일에 토큰을 추가해 주세요".format(configFile))
            safeprint("'{0}' 파일을 열어 봇 토큰 설정 방법을 참고해 주세요".format(configFile))
            safeprint("토큰 설정이 안 된 경우 윈도우 알림 기능만 작동한다에요")
            # exitOnKey()

        # Please use your own client id and secret (https://dev.twitch.tv/)
        self.TWclientID = "b36dxtency2u8jj09wx4tdqgwqk159"
        self.TWclientSecret = ""

        if not self.TGclientID: # Request TGclientID if missing from configFile
            self.TGclientIDs = getClientID(self.botToken)
            self.TGclientID = self.TGclientIDs.get("기본")
        else:
            clientIDSet = True # TGclientID is set from configFile

        if not self.TGclientID: # Exit if failed to fetch TGclientID
            safeprint("클라이언트 아이디 정보가 없어요. 토큰 설정이 잘 못 되었거나 봇에게 먼저 말을 걸어 주세요")
            # safeprint("Unable to fetch client ID. Please make sure bot token is correct or send any message to bot if running for the first time.")
            # exitOnKey()
        else:
            if not clientIDSet:
                safeprint("{}\n텔레그램 클라이언트 아이디 목록\n{}".format("-"*50, "-"*50))

                for k, v in self.TGclientIDs.items():
                    safeprint("'{}' : {}".format(k, v))

                safeprint("{}\n[클라이언트 아이디]: {}".format("-"*50, self.TGclientID))

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
                        "; 텔레그램에서 BotFather를 검색하고 /start 와 /newbot 명령어를 입력해 봇을 만들어 주세요\n" \
                        "; 봇 이름과 봇 계정이름을 입력해 주세요 (여기서 봇 계정이름은 대소문자 구분 없이 bot으로 끝나야 해요)\n" \
                        "; 봇 계정 설정이 끝나면 토큰 값을 보내 주는데 이 값을 복사해서 아래 token 항목에 넣어 주세요\n" \
                        "; **중요: 그리고 본인이 새로 만든 봇을 검색해서 먼저 아무 말이나 대화를 걸어 주세요\n" \
                        "; **(봇을 특정 채널이나 그룹에 초대 한 경우 그 채널 또는 그룹에서도 대화를 시작해 주세요)\n" \
                        "\n" \
                        "; <token>\n" \
                        "; 텔레그램 봇을 만들면 아래와 같은 형식의 토큰을 생성해 줘요. 토큰을 받아서 설정해 주세요\n" \
                        "; token = 110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw\n" \
                        "\n" \
                        "; <clientid> 텔레그램 클라이언트 아이디\n" \
                        "; 필수 설정 사항은 아니며 설정하지 않은 경우 프로그램 실행시 자동으로 받아 와요\n" \
                        "; 하지만 주기적으로 봇에게 말을 다시 걸어 줘야 정상 작동하기 때문에 클라이언트 아이디를 직접 설정해 주길 권장해요\n" \
                        "; 프로그램 실행 시 콘솔창에 아래와 같이 본인의 기본 클라이언트 아이디와 봇이 참여한 채널/그룹의 클라이언트 아이디를 출력해 줘요\n" \
                        "; 기본(개임메시지)가 아닌 채널 또는 그룹으로 메시지를 받고 싶으면 클라이언트 아이디를 꼭 설정해 주세요\n" \
                        "; (봇이 참여한 채널 또는 그룹이 목록에 안 뜨는 경우 먼저 해당 채널 또는 그룹에서도 대화를 시작해 주세요!)\n" \
                        "; '설정파일 로딩 완료!'\n" \
                        "; --------------------------------------------------\n" \
                        "; 텔레그램 클라이언트 아이디 목록\n" \
                        "; --------------------------------------------------\n" \
                        "; '기본' : 12345678\n" \
                        "; '채널이름1' : -987654321\n" \
                        "; '그룹이름2' : -111222333\n" \
                        "; --------------------------------------------------\n" \
                        "; '[클라이언트 아이디]: 12345678'\n" \
                        "; clientid = 12345678\n" \
                        "\n" \
                        "; <userlist> 일반 알리미 유저 목록 파일\n" \
                        "; 해당 파일에 알림을 받을 스트리머의 로그인 아이디를 한줄에 한명씩 추가해 주세요\n" \
                        "; 이 목록은 실시간으로 수정이 반영되므로 프로그램 실행중 언제든지 추가 및 삭제가 가능해요\n" \
                        "; userlist = [일반] 알림목록.txt\n" \
                        "; 알리미 실행 파일과 위치가 다를 경우 파일 전체 경로를 설정해 주세요\n" \
                        "; userlist = C:\\Users\\cooluser\\Desktop\\직박구리\\레전드.txt\n" \
                        "\n" \
                        "; <userpriority> 속성 알리미 유저 목록 파일\n" \
                        "; 해당 파일에 알림을 받을 스트리머의 로그인 아이디를 한줄에 한명씩 추가해 주세요\n" \
                        "; 이 목록은 실시간으로 수정이 반영되므로 프로그램 실행중 언제든지 추가 및 삭제가 가능해요\n" \
                        "; userpriority = [속성] 알림목록.txt\n" \
                        "; 알리미 실행 파일과 위치가 다를 경우 파일 전체 경로를 설정해 주세요\n" \
                        "; userpriority = C:\\Users\\cooluser\\Desktop\\찌르레기\\전설.txt\n" \
                        "\n" \
                        "; <sendthumbnail> 썸네일 사용 여부\n" \
                        "; 텔레그램 문자에 방송 썸네일을 같이 전송해요 (썸네일 평균 용량은 20-40kb 정도해요)\n" \
                        "; 속성 알림은 썸네일을 지원하지 않아요\n" \
                        "; 썸네일을 포함한 메시지를 전송해요\n" \
                        "; sendthumbnail = True\n" \
                        "; 썸네일 없이 메시지만 전송해요\n" \
                        "; sendthumbnail = False\n" \
                        "\n" \
                        "; <refreshdelay> 일반 목록 갱신 대기 시간(초)\n" \
                        "; 트위치 API를 통해 생방송 여부를 확인하고 다음 확인 때까지 대기시간이에요\n" \
                        "; 빠르게 재요청해도 서버에서 정보 업데이트를 바로 안 해주기 때문에 20~60초 사이의 딜레이를 권장해요\n" \
                        "; refreshdelay = 30\n" \
                        "\n" \
                        "; <refreshpriority> 속성 목록 갱신 대기 시간(초)\n" \
                        "; 트위치 API를 통해 생방송 여부를 개별적으로 확인하고 다음 확인 때까지 대기시간이에요\n" \
                        "; 서버에 부담을 줄이기 위해 10-20초 (최소 3) 사이의 대기시간을 권장해요\n" \
                        "; refreshpriority = 10\n" \
                        "\n" \
                        "; <newalertsonly> 프로그램 시작시 진행중인 방송 알림 여부\n" \
                        "; 프로그램 실행 후 새로운 방송만 알림을 받아요\n" \
                        "; newalertsonly = True\n" \
                        "; 프로그램 실행 후 현재 진행중인 방송도 알림을 받아요\n" \
                        "; newalertsonly = False\n" \
                        "\n" \
                        "; <alertchange> 유저 변경 사항 알림 여부\n" \
                        "; 유저의 아이디, 닉네임, 등급(제휴 파트너) 등 변경 사항을 알려드려요\n" \
                        "; 변경 사항 알림을 받아요\n" \
                        "; alertchange = True\n" \
                        "; 변경 사항 알림을 받지 않아요\n" \
                        "; alertchange = False\n" \
                        "\n" \
                        "; <winnotify> 윈도우 알림 여부 (윈10 이상만 지원)\n" \
                        "; 방송 시작시 윈도우 알림을 받아요\n" \
                        "; 윈도우 알림 기능을 사용해요\n" \
                        "; winnotify = True\n" \
                        "; 윈도우 알림 기능을 사용하지 않아요\n" \
                        "; winnotify = False\n" \
                        "\n" \
                        "; <silentstart> 프로그램 시작 시 텔레그램 문자 알림 여부\n" \
                        "; 프로그램 시작 시 메시지를 받아요\n" \
                        "; silentstart = False\n" \
                        "; 프로그램 시작 시 메시지를 받지 않아요\n" \
                        "; silentstart = True\n" \
                        "\n" \
                        "; <logconsole> 콘솔 로그 파일\n" \
                        "; 콩솔창의 출력 내용을 저장하지 않아요\n" \
                        "; logconsole = \n" \
                        "; 콩솔창의 출력 내용을 console.log 파일에 저장해요\n" \
                        "; logconsole = console.log\n" \
                        "\n" \
                        "; <localtimezone> 알림 표준 시간대 설정\n" \
                        "; 알림 시간을 설정한 시간대로 표시해 줘요\n" \
                        "; 설정 가능한 시간대 목록은 아래 링크에서 확인해 주세요\n" \
                        "; https://en.wikipedia.org/wiki/List_of_tz_database_time_zones\n" \
                        "; 설정하지 않은 경우 현재 사용하는 시스템 시간으로 표시 되어요\n" \
                        "; localtimezone = \n" \
                        "; LA 현지 시간으로 표시 되어요. (제가 LA에 있었을 때...)\n" \
                        "; localtimezone = America/Los_Angeles\n" \
                        "\n"

            safeprint("설정파일 생성중...")

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
                "alertchange" : "True",
                "winnotify": "True",
                "\nsilentstart": "False",
                "logconsole": "",
                "localtimezone": ""
            }

            with open(fileName, 'w', encoding="utf-8") as configfile:
                configfile.write(configString)
                config.write(configfile)
                safeprint("'{0}' 파일을 열어 먼저 설정해 주세요".format(fileName))

            return True

    # Read and load config
    def loadConfig(self):
        try:
            if "LiveAlertConfig" in config:
                self.botToken = config["LiveAlertConfig"].get("token", "")
                self.TGclientID = config["LiveAlertConfig"].get("clientid", "")
                self.userListFile = config["LiveAlertConfig"].get("userlist", "[일반] 알림목록.txt")
                self.userPriority = config["LiveAlertConfig"].get("userpriority", "[속성] 알림목록.txt")
                self.sendThumb = config["LiveAlertConfig"].getboolean("sendthumbnail", True)
                self.refresh = int(config["LiveAlertConfig"].get("refreshdelay", 30))
                self.refresh2 = int(config["LiveAlertConfig"].get("refreshpriority", 10))
                self.newAlertsOnly = config["LiveAlertConfig"].getboolean("newalertsonly", True)
                self.alertChange = config["LiveAlertConfig"].getboolean("alertchange", True)
                self.notification = config["LiveAlertConfig"].getboolean("winnotify", True)
                self.silentstart = config["LiveAlertConfig"].getboolean("silentstart", False)
                self.localTimeZone = config["LiveAlertConfig"].get("localtimezone", "")
                safeprint("설정파일 로딩 완료!")
        except Exception as e:
            safeprint("Error: {}".format(e))

    # Get userData from list of loginIDs or userIDs using Helix API
    def getUserDatafromIDs(self, IDList, userIDLookup=False):
        maxURLSize = 99
        lowerIndex = 0
        userData = {}

        if IDList:
            while lowerIndex < len(IDList): # Loop through IDList and update streamData information
                url = "https://api.twitch.tv/helix/users?"
                upperIndex = min(lowerIndex + maxURLSize, len(IDList))

                for k in IDList[lowerIndex:upperIndex]:
                    if userIDLookup:
                        url += "id=" + k + "&"
                    else:
                        url += "login=" + k + "&"

                if url[-1] == "&":
                    url = url[:-1]

                lowerIndex += maxURLSize
                info = getAPIResponse(url, clientID=self.TWclientID, token=OAuthToken)

                if info:
                    btype = {"" : "0", "affiliate" : "1", "partner" : "2"}

                    for n in info["data"]:
                        if userIDLookup:
                            userData[n.get("id")] = [n.get("login"), n.get("display_name"), btype.get(n.get("broadcaster_type")), False, [n.get("streamID")] if n.get("streamID") else []] # userID: [loginID, displayName, broadcasterType, live, [streamID]]
                        else:
                            userData[n.get("login")] = [n.get("id"), n.get("display_name"), btype.get(n.get("broadcaster_type")), False, None, [n.get("streamID")] if n.get("streamID") else []] # loginID: [userID, displayName, broadcasterType, live, time, [streamID]]

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
        validate = {}
        added = []
        dataResponse = {}
        fillerID = "twitch"
        popFiller = False

        if priority:
            loginIDList = fileToList(self.userPriority, removeDuplicate=True)
            userHash = self.listHashP
        else:
            loginIDList = fileToList(self.userListFile, removeDuplicate=True)
            userHash = self.listHashN

        # Remove from self.changedID once loginID is added to the alert list
        for n in loginIDList:
            if n in self.changedID[0 if priority else 1]:
                self.changedID[0 if priority else 1].remove(n)

        # Add changed loginID to continue to track live streams
        loginIDList.extend(self.changedID[0 if priority else 1])

        # Remove non-matching key
        for k in list(userData):
            if k not in loginIDList:
                userData.pop(k, None)
                removed.append(str(k))

        currentHash = hash(str(loginIDList)) # Get list hash

        if (currentHash != userHash and self.needUpdate(loginIDList, userData)) or forced: # Update when hash changes or when forced
            # Add known account for valid dataResponse check
            if len(loginIDList) and fillerID not in loginIDList:
                loginIDList.append(fillerID)
                popFiller = True

            if priority:
                self.listHashP = currentHash
            else:
                self.listHashN = currentHash

            dataResponse = self.getUserDatafromIDs(loginIDList)

            if dataResponse: # Check needed to distinguish from valid response and non API response
                # Add missing key value pair
                for k, v in dataResponse.items():
                    if k not in userData:
                        if not popFiller or k != fillerID:
                            userData.update({k:v})
                            added.append(str(k))
                    else: # Detect displayName and broadcasterType change
                        if self.alertChange:
                            if v[1] != userData.get(k)[1]: # Update displayName
                                self.changeData.append([k, v[1], userData.get(k)[1], "", ""]) # [loginID, displayName, prechange-displayName, typeChange, prechange-loginID]
                                userData.get(k)[1] = v[1]

                            if v[2] != userData.get(k)[2]: # Update broadcasterType
                                self.changeData.append([k, v[1], "", userData.get(k)[2] + v[2], ""]) # [loginID, displayName, prechange-displayName, typeChange, prechange-loginID]
                                userData.get(k)[2] = v[2]

                # Validate invalid key value pair from userData (either username has changed or banned)
                for k, v in userData.items():
                    if k not in dataResponse:
                        validate.update({v[0]:k}) # {userID : loginID}
                        removed.append(k)

                if validate:
                    IDResponse = self.getUserDatafromIDs(list(validate), userIDLookup=True)

                    if IDResponse: # userID: [loginID, displayName, broadcasterType, live, [streamID]]
                        for k, v in IDResponse.items():
                            if validate.get(k):
                                self.changeData.append([v[0], v[1], "", "", validate.get(k)]) # [loginID, displayName, prechange-displayName, typeChange, prechange-loginID]
                                userData.update({v[0]:[k, v[1], v[2], v[3], userData.get(validate.get(k))[4]]}) # Add new loginID to userData
                                added.append(v[0])

                                if v[0] not in self.changedID[0 if priority else 1]:
                                    self.changedID[0 if priority else 1].append(v[0]) # Track changed loginID

                for k in removed:
                    userData.pop(k, None)

            # Remove fillerID after use
            if popFiller:
                loginIDList.remove(fillerID)

        listType = "[속성] " if priority else "[일반] "

        if added or removed:
            safeprint("{0} {1}알리미 목록이 업데이트 되었다에요 [{2}]".format(timeStamp(), listType, len(userData)))

            if removed:
                safeprint("{0} {1}목록에서 {2} 명을 삭제했다에요\n{3}\n".format(timeStamp(), listType, len(removed), removed))
            if added:
                safeprint("{0} {1}목록에 {2} 명을 추가했다에요\n{3}\n".format(timeStamp(), listType, len(added), added))

            missing = [n for n in loginIDList if n not in userData]

            if missing:
                safeprint("{0} 다음 {1}목록의 아이디를 조회할 수 없어요. 다시 확인해 주세요\n{2}".format(timeStamp(), listType, missing))

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

    # Returns updated userData and streamData in the form { userID: [displayName, streamTitle, timeStamp, viewerCount, gameID, streamID], ... }
    def getLiveResponse(self, userData):
        loginIDList = list(userData.keys())

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

            # Reset live state
            for k in userData:
                userData.get(k)[3] = False

            if info:
                for n in info["data"]:
                    match = self.searchForValue(userData, n.get("user_id"))

                    if match:
                        streamID = n.get("id")
                        streamTime = n.get("started_at")

                        if streamID:
                            userData.get(match)[3] = True

                            if streamID not in userData.get(match)[-1]: # New streamID
                                if len(userData.get(match)[-1]) > 4: # Keep last 5 streamIDs
                                    userData.get(match)[-1].pop(0)

                                if streamTime:
                                    timeStampUTC = round(datetime.fromisoformat(streamTime.replace("Z", "+00:00")).timestamp())

                                    if timeStampUTC:
                                        userData.get(match)[4] = timeStampUTC

                                userData.get(match)[-1].append(streamID)
                                streamData[match] = [n.get("user_name"), n.get("title"), n.get("started_at"), n.get("viewer_count"), n.get("game_id"), streamID]

        # Build gameID to gameName dictionary
        if streamData:
            self.getGameResponse(streamData)

        return streamData, userData

    # Build and send message
    def buildMessage(self, streamData, sendThumb=True):
        # Skip messaging on first run if newAlertsOnly is set to true
        if self.newAlertsOnly:
            self.newAlertsOnly = False
            return

        if streamData: # userID: [displayName, streamTitle, timeStamp, viewerCount, gameID, streamID]
            eye = u'\U0001F441'

            for n in streamData:
                timeStr = convertUTCtoLocalTime(streamData.get(n)[2], localTimeZone=self.localTimeZone)
                thumbURL = "https://static-cdn.jtvnw.net/previews-ttv/live_user_{0}-640x360.jpg?a={1}".format(n, time.time())
                category = self.gameData.get(streamData.get(n)[4], "")
                timeStampUTC = round(datetime.fromisoformat(streamData.get(n)[2].replace("Z", "+00:00")).timestamp())
                hashStr = "{}_{}_{}".format(n, streamData.get(n)[5], timeStampUTC)
                hashSha1 = hashlib.sha1(hashStr.encode()).hexdigest()[:20]

                if category:
                    category = "<a href='https://www.twitch.tv/directory/game/{gameHTML}'>{game}</a>".format(gameHTML=quote(category, safe=''), game=escape(category))
                else:
                    category = "-"

                messagePrint = "{} ({}) ({} 명 시청중)\n".format(streamData.get(n)[0], n, streamData.get(n)[3]) + \
                                "시작: {} ({} 경과)\n".format(timeStr[0], timeStr[1]) + \
                                "방제: '{}'\n".format(streamData.get(n)[1].strip()) + \
                                "범주: '{}'\n".format(self.gameData.get(streamData.get(n)[4], "-")) + \
                                "\n{}_{}".format(hashSha1, hashStr)

                message = "<a href='https://www.twitch.tv/{loginID}'>{displayName} ({loginID})</a> ({eye} <i>{view}</i>)\n".format(loginID=n, displayName=streamData.get(n)[0], eye=eye, view=streamData.get(n)[3]) + \
                            "시작: {} (<i>{}</i> 경과)\n".format(timeStr[0], timeStr[1]) + \
                            "방제: <b>{}</b>\n".format(escape(streamData.get(n)[1].strip())) + \
                            "범주: {}".format(category)

                safeprint("{0}\n{1} {2}\n{3}".format("-"*50, timeStamp(), messagePrint, "-"*50))

                if self.notification:
                    winNotify(kwargs=dict(displayName=streamData.get(n)[0], loginID=n, startTime=timeStr[0], elapsed=timeStr[1], title=streamData.get(n)[1].strip(), game=self.gameData.get(streamData.get(n)[4], "-")))

                rval = False

                if sendThumb:
                    rval = sendPhoto(self.botToken, self.TGclientID, thumbURL, message)
                else:
                    rval = sendMessage(self.botToken, self.TGclientID, message)

                if not rval:
                    safeprint("{0} 텔레그램 메시지 전달이 늦거나 실패할 수 있다에요...".format(timeStamp()))

                time.sleep(2) # Give some delay between consecutive alerts

    # Build and send notification when displayName or broadcasterType changes
    def notifyUserChange(self):
        if self.changeData: # [loginID, displayName, prechange-displayName, typeChange, prechange-loginID]
            arrow = u'\U0000279C'

            for n in self.changeData:
                types = ["일반", "제휴", "파트너"]

                if n[3]: # broadcasterType change
                    change = int(n[3][0]) - int(n[3][1])

                    messagePrint = "{} ({})\n".format(n[1], n[0]) + \
                                    "[{}] {} [{}] 회원이 되었어요{}\n".format(types[int(n[3][0])], arrow, types[int(n[3][1])], ("..." if change > 0 else "!")) + \
                                    "{}".format("강등 되었다에요..ㅠㅠ" if change > 0 else "구독 '해줘'")

                    message = "<a href='https://www.twitch.tv/{loginID}'>{displayName} ({loginID})</a>\n".format(displayName=n[1], loginID=n[0]) + \
                                "[{}] {} [{}] 회원이 되었어요{}\n".format(types[int(n[3][0])], arrow, types[int(n[3][1])], ("..." if change > 0 else "!")) + \
                                "{}".format("강등 되었다에요..ㅠㅠ" if change > 0 else "구독 '해줘'")

                    if self.notification:
                        winNotify(kwargs=dict(displayName=n[1], loginID=n[0], btype=n[3]))
                elif n[4]: # loginID change
                    messagePrint = "{} ({})\n".format(n[1], n[0]) + \
                                    "[{}] {} [{}]\n".format(n[4], arrow, n[0]) + \
                                    "아이디가 변경 되었어요! 알림 목록 파일을 수정해 주세요"

                    message = "<a href='https://www.twitch.tv/{loginID}'>{displayName} ({loginID})</a>\n".format(displayName=n[1], loginID=n[0]) + \
                                "[{}] {} [{}]\n".format(n[4], arrow, n[0]) + \
                                "아이디가 변경 되었어요!"

                    if self.notification:
                        winNotify(kwargs=dict(displayName=n[1], loginID=n[0], oldID=n[4]))
                else: # displayName change
                    messagePrint = "{} ({})\n".format(n[1], n[0]) + \
                                    "[{}] {} [{}]\n".format(n[2], arrow, n[1]) + \
                                    "닉네임이 변경 되었어요! 이건 굉장히 귀하네요"

                    message = "<a href='https://www.twitch.tv/{loginID}'>{displayName} ({loginID})</a>\n".format(displayName=n[1], loginID=n[0]) + \
                                "[{}] {} [{}]\n".format(n[2], arrow, n[1]) + \
                                "닉네임이 변경 되었어요!\n이건 굉장히 귀하네요"

                    if self.notification:
                        winNotify(kwargs=dict(displayName=n[1], loginID=n[0], oldName=n[2]))

                    for t in threading.enumerate(): # Stop thread with old displayName
                        if t.name != "MainThread" and t.name == n[0]:
                            t.stop()

                safeprint("{0}\n{1} {2}\n{3}".format("-"*50, timeStamp(), messagePrint, "-"*50))

                if not sendMessage(self.botToken, self.TGclientID, message):
                    safeprint("{0} 텔레그램 메시지 전달이 늦거나 실패할 수 있다에요...".format(timeStamp()))

                time.sleep(2) # Give some delay between consecutive alerts

            self.changeData.clear()

    # Keyboard event
    def keyPressEvent(self):
        key = kbFunc()

        if key == 49: # 1
            self.printLiveResponse()
        elif key == 50: # 2
            self.printUserList(priority=True) # priority
        elif key == 51: # 3
            self.printUserList()
        # elif key > 0: # Print key
            # safeprint(key)

    # Print live streams
    def printLiveResponse(self):
        _, self.priorityData = self.getLiveResponse(self.priorityData)
        message = ""
        onlineList = []

        for k in self.priorityData:
            if k not in onlineList and self.priorityData.get(k)[3]:
                onlineList.append(k)
                hashStr = "{}_{}_{}".format(k, self.priorityData.get(k)[-1][-1], self.priorityData.get(k)[4])
                hashSha1 = hashlib.sha1(hashStr.encode()).hexdigest()[:20]
                message += "{} ({}) [{}_{}]\n".format(self.priorityData.get(k)[1], k, hashSha1, hashStr)

        for k in self.userData:
            if k not in onlineList and self.userData.get(k)[3]:
                onlineList.append(k)
                hashStr = "{}_{}_{}".format(k, self.userData.get(k)[-1][-1], self.userData.get(k)[4])
                hashSha1 = hashlib.sha1(hashStr.encode()).hexdigest()[:20]
                message += "{} ({}) [{}_{}]\n".format(self.userData.get(k)[1], k, hashSha1, hashStr)

        if message:
            safeprint("{}\n{} 현재 방송 중...[{}]\n{}\n{}{}".format("-"*50, timeStamp(), len(onlineList), "-"*50, message, "-"*50))
        else:
            safeprint("{}\n{} 진행 중인 방송이 없다에요ㅠㅠ\n{}".format("-"*50, timeStamp(), "-"*50))

    # Print user list
    def printUserList(self, priority=None):
        if priority:
            userData = self.priorityData
        else:
            userData = self.userData

        checkStr = ""
        count = 0

        for k, v in userData.items():
            if count > 0:
                checkStr += "\n" if count % 4 == 0 else "\t"

            count += 1
            checkStr += "[{} ({})]".format(v[1], k)

        if checkStr:
            safeprint("{}\n{} [{}] 확인 중인 목록...\n{}\n{}\n{}".format("-"*50, timeStamp(), "속성" if priority else "일반", "-"*50, checkStr, "-"*50))
        else:
            safeprint("{}\n{} [{}] 목록이 비어 있다에요\n{}".format("-"*50, timeStamp(), "속성" if priority else "일반", "-"*50))

    # Print list of live streams on start (when newalertsonly is set to true)
    def runOnce(self):
        if self.runOnStart:
            if self.initialAlert:
                self.printLiveResponse()

            self.runOnStart = False

    def createAlertFile(self, fileName):
        if not isfile(fileName):
            safeprint("'{0}' 알림 목록 파일이 존재하지 않아 생성한다에요...".format(fileName))

            try:
                # Create directories if missing
                directory = dirname(fileName)

                if directory and not exists(directory):
                    makedirs(directory)

                open(fileName, "w").close() # Create file
                safeprint("'{0}' 파일을 열어 스트리머의 로그인 아이디를 한줄에 한명씩 추가해 주세요".format(fileName))
                safeprint("이 목록은 실시간으로 수정이 반영 되어요\n")
            except OSError as e:
                safeprint("Error: {}".format(str(e)))
                safeprint("'{0}' 파일 생성에 실패했어요. 파일 경로를 다시 확인해 주라에요".format(fileName))
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
        safeprint("{} 트위치 생방알리미 시작!".format(timeStamp()))

        if not self.silentstart:
            sendMessage(self.botToken, self.TGclientID, "{0} 트위치 생방알리미 시작!\n[일반] | [썸네일 <i>{1}</i>] [{stopwatch} <i>{2}</i>초]\n[속성] | [{stopwatch} <i>{3}</i>초]".format(timeStamp(), "ON" if self.sendThumb else "OFF", self.refresh, self.refresh2, stopwatch=stopwatch))

        if not validateOAuthToken(self.TWclientID):
            # safeprint("{} Need to get valid OAuth Token".format(timeStamp()))
            safeprint("{} 유효한 인증 토큰이 필요해요".format(timeStamp()))
            getOAuthToken(self.TWclientID, self.TWclientSecret)

        OAuthToken = setOAuthToken(self.TWclientID)
        activePriority = []

        # Unset self.localTimeZone to if invalid
        try:
            ZoneInfo("Etc/UTC") # Init

            if self.localTimeZone:
                ZoneInfo(self.localTimeZone)
                safeprint("{} 알림 표준 시간대: '{}'".format(timeStamp(), self.localTimeZone))
        except:
            safeprint("{} 알림 표준 시간대 (localtimezone) 설정이 잘 못 되었다에요: '{}'".format(timeStamp(), self.localTimeZone))
            self.localTimeZone = ""
            pass

        while True:
            if needOAuthUpdate:
                safeprint("{} 인증 토큰 업데이트가 필요해요...".format(timeStamp()))
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

            if self.priorityData: # loginID: [userID, displayName, broadcasterType, live, time, [streamID]]
                currentThreads = [t.name for t in threading.enumerate() if t.name != "MainThread"]

                for n in self.priorityData:
                    if n not in currentThreads: # Start missing thread
                        userInfo = self.priorityData.get(n)

                        if userInfo:
                            ChannelLoopThread(name=n, kwargs=dict(userID=userInfo[0],
                                                                displayName=userInfo[1],
                                                                sleep=self.refresh2,
                                                                newAlertsOnly=(True if n in activePriority else self.initialAlert),
                                                                winnotify=self.notification,
                                                                TWclientID=self.TWclientID,
                                                                botToken=self.botToken,
                                                                TGclientID=self.TGclientID,
                                                                localTimeZone=self.localTimeZone))

                            # Append to activePriority to prevent extra alert when restarting thread due to name change
                            if n not in activePriority:
                                activePriority.append(n)

            # Clear old data from activePriority to prevent alert suppression upon re-addition
            for k in activePriority:
                if k not in self.priorityData:
                    activePriority.remove(k)

            # Update userData
            self.userData = self.updateUserData(self.userData, forced=forceUpdate, priority=False)

            if self.userData:
                streamData, self.userData = self.getLiveResponse(self.userData)
                self.buildMessage(streamData, self.sendThumb)

            # Notify loginID, displayName or broadcasterType changes
            self.notifyUserChange()

            # Print live streams on start (when newalertsonly is set to true)
            self.runOnce()

            if forceUpdate:
                forceUpdate = False

            forceCount += 1

            t0 = time.time()

            while time.time() - t0 < self.refresh:
                self.keyPressEvent()
                time.sleep(0.2)

def main():
    try:
        signal.signal(signal.SIGINT, signalHandler)
        winNotify(kwargs=dict()) # init notification
        liveAlert = TwitchLiveAlert()
        liveAlert.loopLiveAlert(liveAlert.userListFile, liveAlert.userPriority)
    except Exception:
        safeprint("{} Main thread error!".format(timeStamp()))
        traceback.print_exc()
        msvcrt.getch()

if __name__ == "__main__":
    setpriority()
    appName = "생방알리미"
    AUMID = "TLA.TwitchLiveAlert"
    TLAversion = "v2.5"
    configFile = "알리미설정.ini"
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning) # Suppress warning messages
    needOAuthUpdate = False
    OAuthToken = ""
    printLock = threading.Lock()
    logConsole = ""

    # Read config
    config = configparser.ConfigParser()

    try:
        config.read(configFile, encoding="utf_8_sig")

        if "LiveAlertConfig" in config:
            logConsole = config["LiveAlertConfig"].get("logconsole", "")
    except:
        pass

    # Enable console logging
    if logConsole:
        logging.basicConfig(level=logging.INFO, format="{message}", style='{',
                            handlers=[logging.FileHandler(logConsole, "a", "utf-8"), logging.StreamHandler(sys.stdout)])

    Logo = resourcePath("bt.ico")
    CACert = resourcePath("certifi/cacert.pem")
    baseLib = resourcePath("base_library.zip")

    if getattr(sys, 'frozen', False): # Bundle
        appPath = dirname(sys.executable) # Frozen exe path
        exeName = splitext(basename(sys.executable))[0]

        # Lock files
        os.open(Logo, os.O_RDONLY)
        os.open(CACert, os.O_RDONLY)
        os.open(baseLib, os.O_RDONLY)
    else:
        appPath = dirname(__file__) # Script path
        exeName = appName

    os.system("title {}".format(exeName))

    main()
