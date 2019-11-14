# 트위치 생방 알리미

![썸네일 모드](https://i.imgur.com/WAZiAGw.jpg)

트위치 생방알리미는 스트리머가 생방을 시작했을 경우 텔레그램을 통해 문자 알림을 보내주는 프로그램입니다

알림을 받을 수 있는 숫자나 시간 같은 특별한 제한은 없고 팔로우를 하지 않은 스트리머도 알림을 받을 수 있읍니다

프로그램을 실행하고 켜두면 일정시간마다 트위치 API를 이용해 생방 여부를 확인해 주고 보통 생방 시작 후 45초에서 1분30초 사이에 알림을 받습니다

생방알리미는 파이썬(Python 3.7.4)을 기반으로 만들어졌읍니다

윈도우용 실행 파일은 PyInstaller로 제작 됐고 64비트 환경에서만 작동합니다

프로그램이 실행되지 않는경우 MSVC++ 2015 Redistributable x64 런타임을 설치해 주세요
- [Microsoft Visual C++ 2015 Redistributable Package (x64)](https://www.microsoft.com/ko-KR/download/details.aspx?id=52685)


# 사용방법

1. [텔레그램 봇 생성 방법](#텔레그램-봇-생성-방법)을 참고해 봇을 생성하고 토큰을 받습니다

2. 봇을 만들고 해당 봇에게 먼저 대화를 시작해줘야 정상적으로 메시지를 전달 받을 수 있읍니다

3. [`livealert.ini` 설정](#livealertini-설정-파일) 파일을 열어 설정합니다

4. [`livealert.txt` 목록](#livealerttxt-목록-파일) 파일에 알림을 받을 스트리머의 아이디를 한줄에 한명씩 추가해주세요


`livealert.ini` 파일이 없는 경우 `생방알리미.exe` 실행시 자동으로 생성됩니다

(`livealert.ini` 파일의 인코딩은 UTF-8로 유지해주세요. BOM 여부는 상관없읍니다)



프로그램을 시작하고 정상작동 한다면 ***`트위치 생방알리미 시작!`*** 이라는 메시지를 텔레그램으로 받습니다

프로그램을 켜두면 주기적으로 설정된 스트리머들의 생방 여부를 검사하고 알림을 보내줍니다




# 텔레그램 봇 생성 방법

![참고 이미지](https://i.imgur.com/soxLdbJ.jpg)


텔레그램에서 [BotFather](https://telegram.me/botfather)를 검색하고 `/start` 와 `/newbot` 명령어를 입력해 봇을 만들어 줍니다

봇 이름과 봇 계정이름을 입력 해줍니다 (여기서 봇 계정이름의 끝은 대소문자 구별없이 ***bot***으로 끝나야 합니다)

봇 계정 설정이 끝나면 아래와 같은 형식의 토큰 값을 보내주는데 이 값을 복사해서 `livealert.ini` 파일의 `token` 항목에 붙여넣습니다

`110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw`

**그리고 본인이 새로 만든 봇을 검색해서 먼저 아무 말이나 대화를 걸어 줘야합니다**


# `livealert.ini` 설정 파일

```ini
[LiveAlertConfig]
token = 
clientid = 
userlist = livealert.txt
sendthumbnail = True
refreshdelay = 30
newalertsonly = True
```

#### `token` 텔레그램 봇 생성 후 받은 토큰

```ini
token = 110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
```

#### `clientid` 텔레그램 클라이언트 아이디

필수 설정 사항은 아니며 설정하지 않은 경우 프로그램 실행시 자동으로 받아와 콘솔창에 아래와 같이 본인의 클라이언트 아이디를 출력해줍니다

```ini
설정파일 로딩 완료!
[클라이언트 아이디]: 12345678
```

가끔씩 봇에게 말을 다시 걸어줘야 정상 작동하는 경우가 있는데 클라이언트 아이디를 직접 설정해주면 그런 현상이 줄어드니 설정을 권장합니다
```ini
clientid = 12345678
```

#### `userlist` 알리미 유저 목록 파일 이름

해당 파일에 알림을 받을 스트리머의 로그인 아이디를 한줄에 한명씩 추가합니다

이 목록은 실시간으로 수정이 반영되므로 프로그램 실행중 언제든지 추가 및 삭제가 가능합니다
```ini
userlist = livealert.txt
```

알리미 실행 파일과 위치가 다를 경우 파일 전체 경로를 설정해주세요
```ini
userlist = C:\Users\cooluser\Desktop\직박구리\레전드.txt
```

#### `sendthumbnail` 썸네일 사용 여부

썸네일을 포함한 메시지를 전송합니다 (썸네일 평균 용량은 20-40kb 정도입니다)
```ini
sendthumbnail = True
```

썸네일 없이 메시지만 전송합니다
```ini
sendthumbnail = False
```

#### `refreshdelay` 갱신 대기 시간(초)

트위치 API를 통해 생방송 여부를 확인하고 다음 확인때까지 대기시간입니다

빠르게 재요청해도 서버에서 정보 업데이트를 바로 안 해주기 때문에 20~60초 사이의 딜레이를 권장합니다

```ini
refreshdelay = 30
```

#### `newalertsonly` 프로그램 시작시 진행중인 방송 알림 여부

프로그램 실행 후 새로운 방송만 알림을 받습니다
```ini
newalertsonly = True
```

프로그램 실행 후 현재 진행중인 방송도 알림을 받습니다
```ini
newalertsonly = False
```

# `livealert.txt` 목록 파일

해당 파일에 알림을 받을 아이디를 한줄에 하나씩 입력해 주세요

```
zilioner
hanryang1125
mbcmlt1
starcraft_kr
lck_korea
playoverwatch_kr
teaminven
```
