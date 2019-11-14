#!/usr/bin/env python3

import sys, signal
import configparser
import msvcrt
from os import makedirs
from os.path import isfile, join, exists, dirname
import requests
import time
from datetime import datetime, timedelta
from html import escape

class TwitchLiveAlert:
    def __init__(self):
        self.ver = "v1.0"
        print("트위치 생방알리미 {0}".format(self.ver))
        signal.signal(signal.SIGINT, self.signalHandler)
        self.userData = {}
        self.gameData = {}
        self.configFile = "livealert.ini"

        if self.createConfig(self.configFile): # Config file created
            self.exitOnKey()

        self.botToken = ""
        self.userListFile = "livealert.txt"
        self.sendThumb = True
        self.refresh = 30
        self.newAlertsOnly = False
        self.loadConfig() # Read and load config

        clientIDSet = False

        if not self.botToken:
            print("현기증 난단 말이에요. 빨리 '{0}' 파일에 토큰을 추가해 주세요".format(self.configFile))
            print("'{0}' 파일을 열어 봇 토큰 설정 방법을 참고해 주세요".format(self.configFile))
            self.exitOnKey()

        self.TWclientID = "b36dxtency2u8jj09wx4tdqgwqk159"

        if not self.TGclientID: # Request TGclientID if missing from configFile
            self.TGclientID = self.getClientID()
        else:
            clientIDSet = True # TGclientID is set from configFile

        if not self.TGclientID: # Exit if failed to fetch TGclientID
            print("클라이언트 아이디 정보가 없습니다. 토큰설정이 잘 못 되었거나 봇에게 먼저 말을 걸어주세요")
            # print("Unable to fetch client ID. Please make sure bot token is correct or send any message to bot if running for the first time.")
            self.exitOnKey()
        else:
            if not clientIDSet:
                print("[클라이언트 아이디]: {0}".format(self.TGclientID))

        print("[목록파일]: {0} | [썸네일 {1}] [갱신대기 {2}초]".format(self.userListFile, "ON" if self.sendThumb else "OFF", self.refresh))

    # Handle system interrupt to break python loop scope
    def signalHandler(self, signal, frame):
        print("\nKeyboard interrupt: Exiting loop...")
        sys.exit()

    # Pause and exit on key press
    def exitOnKey(self):
        print("아무 키나 누르면 종료됩니다 ...")
        msvcrt.getch()
        sys.exit()

    # Create missing config file
    def createConfig(self, fileName):
        if not isfile(fileName): # config file missing
            configString = "; 텔레그램 봇 생성 및 토큰 얻기 https://telegram.me/botfather\n" \
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
                        "; 가끔씩 봇에게 말을 다시 걸어줘야 정상 작동하는 경우가 있는데 클라이언트 아이디를 직접 설정해주면 그런 현상이 줄어듭니다\n" \
                        "; 본인의 클라이언트 아이디는 프로그램을 실행하면 아래와 같은 메시지를 콘솔 창으로 확인할 수 있읍니다\n" \
                        "; '설정파일 로딩 완료!'\n" \
                        "; '[클라이언트 아이디]: 12345678'\n" \
                        "; clientid = 12345678\n" \
                        "\n" \
                        "; <userlist> 알리미 유저 목록 파일\n" \
                        "; 해당 파일에 알림을 받을 스트리머의 로그인 아이디를 한줄에 한명씩 추가합니다\n" \
                        "; 이 목록은 실시간으로 수정이 반영되므로 프로그램 실행중 언제든지 추가 및 삭제가 가능합니다\n" \
                        "; userlist = livealert.txt\n" \
                        "; 알리미 실행 파일과 같은 위치에 없는 경우 파일 전체 경로를 설정해주세요\n" \
                        "; userlist = C:\\Users\\cooluser\\Desktop\\직박구리\\레전드.txt\n" \
                        "\n" \
                        "; <sendthumbnail> 썸네일 사용 여부\n" \
                        "; 썸네일을 포함한 메시지를 전송합니다 (썸네일 평균 용량은 20-40kb 정도입니다)\n" \
                        "; sendthumbnail = True\n" \
                        "; 썸네일 없이 메시지만 전송합니다\n" \
                        "; sendthumbnail = False\n" \
                        "\n" \
                        "; <refreshdelay> 갱신 대기 시간(초)\n" \
                        "; 트위치 API를 통해 생방송 여부를 확인하고 다음 확인때까지 대기시간입니다\n" \
                        "; 빠르게 재요청해도 서버에서 정보 업데이트를 바로 안 해주기 때문에 20~60초 사이의 딜레이를 권장합니다\n" \
                        "; refreshdelay = 30\n" \
                        "\n" \
                        "; <newalertsonly> 프로그램 시작시 진행중인 방송 알림 여부\n" \
                        "; 프로그램 실행 후 새로운 방송만 알림을 받습니다\n" \
                        "; newalertsonly = True\n" \
                        "; 프로그램 실행 후 현재 진행중인 방송도 알림을 받습니다\n" \
                        "; newalertsonly = False\n" \
                        "\n"

            print("설정파일 생성중 ...")
            config = configparser.ConfigParser()

            # Default output
            config["LiveAlertConfig"] = {
                "token": "",
                "clientid": "",
                "userlist": "livealert.txt",
                "sendthumbnail": "True",
                "refreshdelay": "30",
                "newalertsonly": "True"
            }

            with open(fileName, 'w', encoding="utf-8") as configfile:
                configfile.write(configString)
                config.write(configfile)
                print("'{0}' 파일을 열어 먼저 설정해주세요".format(fileName))

            return True

    # Read and load config
    def loadConfig(self):
        config = configparser.ConfigParser()

        try:
            config.read(self.configFile, encoding="utf_8_sig")

            if 'LiveAlertConfig' in config:
                self.botToken = config["LiveAlertConfig"].get("token", "")
                self.TGclientID = config["LiveAlertConfig"].get("clientid", "")
                self.userListFile = config["LiveAlertConfig"].get("userlist", "")
                self.sendThumb = config["LiveAlertConfig"].getboolean("sendthumbnail", True)
                self.refresh = int(config["LiveAlertConfig"].get("refreshdelay", 30))
                self.newAlertsOnly = config["LiveAlertConfig"].getboolean("newalertsonly", False)
                print("설정파일 로딩 완료!")
        except:
            pass

    # Print current date and time
    def timeStamp(self, format = None):
        now = datetime.now()

        if format is None:
            format = "[%y-%m-%d %H:%M:%S]"

        date_string = now.strftime(format)

        return date_string

    # Returns valid API response
    def getAPIResponse(self, url, kraken=None, token=None, ignoreHeader=None, data=None, returnError=None, printError=None, post=None):
        header = None

        if not ignoreHeader:
            header = {}

            if kraken: # Extra header for Kraken API
                header.update({'Accept' : "application/vnd.twitchtv.v5+json"})
                header.update({'Client-ID' : self.TWclientID})

                if token:
                    header.update({'Authorization' : "OAuth " + token})
            else:
                if token:
                    header.update({'Authorization' : "Bearer " + token})
                else:
                    header.update({'Client-ID' : self.TWclientID})

        try:
            if post: # Update data
                res = requests.post(url, data=data, headers=header, timeout=10)
            else: # Request data
                res = requests.get(url, headers=header, timeout=10)

            # code = res.status_code
            info = res.json()

            if not kraken:
                if info["data"]:
                    return info
            else:
                if info:
                    return info

        except requests.exceptions.RequestException as e:
            if printError: print("Requests Error: " + str(e))
            if returnError: return e
        except:
            pass

        return []

    # Returns user clientID using Telegram getUpdates API
    def getClientID(self):
        clientID = ""
        url = "https://api.telegram.org/bot{0}/{1}".format(self.botToken, "getUpdates")

        res = self.getAPIResponse(url, True, ignoreHeader=True)

        if res:
            try:
                clientID = res["result"][0]["message"]["from"]["id"]
            except:
                pass

        return str(clientID)

    # Telegram sendMessage API
    def sendMessage(self, message):
        url = "https://api.telegram.org/bot{0}/{1}".format(self.botToken, "sendMessage")

        data = {
            "chat_id": self.TGclientID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        res = self.getAPIResponse(url, True, ignoreHeader=True, data=data, returnError=True, post=True)

        if res:
            if not res["ok"]:
                if res["error_code"] == 400:
                    print("메시지 전달 오류: 설정파일이 잘못되었거나 메시지 호환이 안 됩니다")
                    # sys.exit()
                elif res["error_code"] == 403:
                    print("메시지 권한 오류: 봇에게 먼저 대화를 걸어주세요")
                    # sys.exit()
            else:
                return True

        return False

    # Telegram sendPhoto API
    def sendPhoto(self, photo, caption=""):
        url = "https://api.telegram.org/bot{0}/{1}".format(self.botToken, "sendPhoto")

        data = {
            "chat_id": self.TGclientID,
            "photo": photo,
            "caption": caption,
            "parse_mode": "HTML"
        }

        res = self.getAPIResponse(url, True, ignoreHeader=True, data=data, post=True)

        if res:
            if not res["ok"]:
                if res["error_code"] == 400:
                    print("메시지 전달 오류: 설정파일이 잘 못 되었거나 메시지 호환이 안 됩니다")
                    # sys.exit()
                elif res["error_code"] == 403:
                    print("메시지 권한 오류: 봇에게 먼저 대화를 걸어주세요")
                    # sys.exit()
            else:
                return True

        return False

    # Convert time from UTC to local
    def convertUTCtoLocalTime(self, timeStr, format="[%y-%m-%d %I:%M:%S %p]"):
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

    # Get userData from list of loginIDs using Helix API
    def getUserDatafromLoginIDs(self, loginIDList):
        maxURLSize = 99
        lowerIndex = 0
        userData = {}

        if loginIDList:
            while lowerIndex < len(loginIDList): # Loop through loginIDList and update streamData information
                url = "https://api.twitch.tv/helix/users?"
                upperIndex = min(lowerIndex + maxURLSize, len(loginIDList))

                for k in loginIDList[lowerIndex:upperIndex]:
                    url += "login=" + k + "&"

                if url[-1] == "&":
                    url = url[:-1]

                lowerIndex += maxURLSize

                info = self.getAPIResponse(url)

                if info:
                    for n in info["data"]:
                        userData[n.get("login")] = [n.get("id"), n.get("display_name"), n.get("liveID", "")] # loginID: [userID, displayName, liveID]

        return userData

    # Request UserData API when missing key value pair
    def needUpdate(self, loginIDList):
        for n in loginIDList:
            if n not in self.userData:
                return True

        return False

    # Add or remove loginID from userData
    def updateUserData(self, loginIDList):
        if not loginIDList:
            print("Need list of loginIDs")
            return

        removed = []
        added = []

        # Remove non-matching key
        for k in list(self.userData):
            if k not in loginIDList:
                self.userData.pop(k, None)
                removed.append(str(k))

        if self.needUpdate(loginIDList):
            tempData = self.getUserDatafromLoginIDs(loginIDList)

            # Add missing key value pair
            for k, v in tempData.items():
                if k not in self.userData:
                    self.userData.update({k:v})
                    added.append(str(k))

        if added or removed:
            print("{0} 알리미 목록이 업데이트 되었읍니다".format(self.timeStamp()))

            if removed:
                print("{0} 목록에서 {1} 명을 삭제했읍니다\n{2}".format(self.timeStamp(), len(removed), removed))
            if added:
                print("{0} 목록에 {1} 명을 추가했읍니다\n{2}".format(self.timeStamp(), len(added), added))

            missing = [n for n in loginIDList if n not in self.userData]

            if missing:
                print("{0} 아래 목록의 아이디를 조회할 수 없읍니다. 다시 확인해주세요\n{1}".format(self.timeStamp(), missing))

    def searchForValue(self, dict, searchFor):
        for k in dict:
            for v in dict[k]:
                if searchFor in v:
                    return k
        return None

    # Build gameID to gameName dictionary
    def getGameResponse(self, streamData):
        if not streamData:
            return False

        gameIDs = list(n[4] for n in streamData.values() if n[4] not in self.gameData) # List of gameIDs
        gameIDs = list(set(gameIDs)) # Remove duplicates, no order preserved

        if gameIDs:
            # print("Found new gameIDs: {0}".format(gameIDs))
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

                info = self.getAPIResponse(url)

                if info:
                    for n in info["data"]:
                        if n.get("id") not in self.gameData:
                            self.gameData[n.get("id")] = n.get("name")

        # print("Updated gameData: {0}".format(self.gameData))

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

            info = self.getAPIResponse(url)

            if info:
                for n in info["data"]:
                    match = self.searchForValue(self.userData, n.get("user_id"))
                    if match:
                        if n.get("id") != self.userData.get(match)[2]: # New streamID
                            self.userData.get(match)[2] = n.get("id")
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
                timeStr = self.convertUTCtoLocalTime(streamData.get(n)[2])
                thumbURL = "https://static-cdn.jtvnw.net/previews-ttv/live_user_{0}-640x360.jpg?a={1}".format(n, time.time())
                category = escape(self.gameData.get(streamData.get(n)[4], ""))

                if category:
                    category = "<a href='https://www.twitch.tv/directory/game/{game}'>{game}</a>".format(game=category)
                else:
                    category = "-"

                title = escape(streamData.get(n)[1].strip())

                messagePrint = "{0} ({loginID}) ({view} 명 시청중)\n시작: {2} ({3} 경과)\n방제: '{1}'\n범주: '{game}'".format(streamData.get(n)[0], streamData.get(n)[1].strip(), timeStr[0], timeStr[1], loginID=n, view=streamData.get(n)[3], game=self.gameData.get(streamData.get(n)[4], "-"))
                message = "<a href='https://www.twitch.tv/{loginID}'>{0} ({loginID})</a> ({eye} <i>{view}</i>)\n시작: {2} (<i>{3}</i> 경과)\n방제: <b>{1}</b>\n범주: {game}".format(streamData.get(n)[0], title, timeStr[0], timeStr[1], loginID=n, eye=eye, view=streamData.get(n)[3], game=category)
                print("----------------------------------------------------")
                print("{0} {1}".format(self.timeStamp(), messagePrint))
                print("----------------------------------------------------")

                rval = False

                if sendThumb:
                    rval = self.sendPhoto(thumbURL, message)
                else:
                    rval = self.sendMessage(message)

                if not rval:
                    print("{0} 텔레그램 메시지 전달이 딜레이 될 수 있읍니다...".format(self.timeStamp()))

                time.sleep(2) # Give some delay between consecutive alerts

    # Open and read file
    def readFile(self, fileName, mode="r"):
        try:
            if isfile(fileName):
                with open(fileName, mode, encoding="utf_8_sig") as file:
                    text = file.readlines()

                    if text:
                        return text
        except OSError as e:
            print("Error: " + str(e))

    # Build list from input file
    def fileToList(self, fileName, removeDuplicate=None):
        listItems = []
        content = self.readFile(fileName)

        if content:
            listItems = [n for n in (n.strip().replace("\n","") for n in content) if n]

            if listItems and removeDuplicate:
                listItems = list(dict.fromkeys(listItems)) # Remove duplicates, order preserved

        return listItems

    # Main loop thread
    def loopLiveAlert(self, fileName="livealert.txt", sendThumb=True):
        if not isfile(fileName):
            print("'{0}' 알림 목록 파일이 존재하지 않아 생성합니다 ...".format(fileName))

            try:
                # Create directories if missing
                directory = dirname(fileName)

                if directory and not exists(directory):
                    makedirs(directory)

                open(fileName, "w").close() # Create file
                print("'{0}' 파일을 열어 스트리머의 로그인 아이디를 한줄에 한명씩 추가해 주세요".format(fileName))
                print("이 목록은 실시간으로 수정이 반영됩니다")
            except OSError as e:
                print("Error: " + str(e))
                print("'{0}' 파일 생성에 실패했읍니다. 파일 경로를 다시 확인해 주세요".format(fileName))
                self.exitOnKey()

        print(self.timeStamp(), "트위치 생방알리미 시작!")
        self.sendMessage("{0} 트위치 생방알리미 시작!\n[썸네일 {1}] [갱신대기 {2}초]".format(self.timeStamp(), "ON" if self.sendThumb else "OFF", self.refresh))

        while True:
            userList = self.fileToList(fileName, removeDuplicate=True)

            if userList:
                self.updateUserData(userList)
            if self.userData:
                streamData = self.getLiveResponse()
                self.buildMessage(streamData, sendThumb)

            time.sleep(self.refresh)

def main():
    liveAlert = TwitchLiveAlert()
    liveAlert.loopLiveAlert(liveAlert.userListFile, liveAlert.sendThumb)

if __name__ == "__main__":
    main()
