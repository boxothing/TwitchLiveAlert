# 트위치 생방 알리미

## [생방알리미 v2.3 다운로드](https://github.com/boxothing/TwitchLiveAlert/releases/download/v2.3/TwitchLiveAlert-2.3.zip)

![썸네일 모드](https://i.imgur.com/WAZiAGw.jpg)

![윈도우 알림](https://i.imgur.com/T9NzrWl.png)

트위치 생방알리미는 스트리머가 생방을 시작했을 경우 텔레그램 문자 또는 윈도우 알림을(윈8 이상) 보내주는 프로그램입니다

알림을 받을 수 있는 개수나 시간 같은 특별한 제한은 없고 원하는 스트리머의 아이디만 입력하면 알림을 받을 수 있읍니다

프로그램을 실행하고 켜두면 일정시간마다 트위치 API를 이용해 생방 여부를 확인해 줍니다

일반 알림의 경우 보통 생방 시작 후 45초에서 3분 사이에 알림을 받고

속성 알림의 경우 평균 10초에서 20초 사이에 알림을 받습니다

해당 스트리머의 생방송 알림을 최대한 빨리 받고 싶은 경우 속성 목록을 이용해 주세요

다만 속성 알림의 경우 스트리머의 채널을 개별적으로 확인해기 때문에 트위치 API 서버에 무리가 갈수 있으니 목록은 30명을 초과하지 않도록 권장합니다

생방알리미는 파이썬(Python 3.7.9)을 기반으로 만들어졌읍니다

윈도우용 실행 파일은 PyInstaller로 제작 됐고 64비트 환경에서만 작동합니다

프로그램이 실행되지 않는경우 MSVC++ 2015 Redistributable x64 런타임을 설치해 주세요
- [Microsoft Visual C++ 2015 Redistributable Package (x64)](https://www.microsoft.com/ko-KR/download/details.aspx?id=52685)


# 사용방법

텔레그램 알림을 받지 않고 윈도우 알림만 받을 경우 1번과 2번은 건너뛰고 3번부터 설정해 주세요

1. [텔레그램 봇 생성 방법](#텔레그램-봇-생성-방법)을 참고해 봇을 생성하고 토큰을 받습니다

2. 봇을 만들고 해당 봇에게 먼저 대화를 시작해줘야 정상적으로 메시지를 전달 받을 수 있읍니다

3. [`알리미설정.ini` 설정](#알리미설정ini-설정-파일) 파일을 열어 설정합니다

4. [`[일반] 알림목록.txt` 목록](#일반-알림목록txt-목록-파일) 파일에 알림을 받을 스트리머의 아이디를 한줄에 한명씩 추가해 주세요


`알리미설정.ini` 파일이 없는 경우 `생방알리미.exe` 실행시 자동으로 생성됩니다

(`알리미설정.ini` 파일의 인코딩은 UTF-8로 유지해주세요. BOM 여부는 상관없읍니다)



텔레그램 사용시 프로그램을 시작하고 정상작동 한다면 ***`트위치 생방알리미 시작!`*** 이라는 메시지를 텔레그램으로 받습니다

프로그램을 켜두면 주기적으로 설정된 스트리머들의 생방 여부를 검사하고 알림을 보내줍니다




# 텔레그램 봇 생성 방법

![참고 이미지](https://i.imgur.com/soxLdbJ.jpg)


텔레그램에서 [BotFather](https://telegram.me/botfather)를 검색하고 `/start` 와 `/newbot` 명령어를 입력해 봇을 만들어 줍니다

봇 이름과 봇 계정이름을 입력 해줍니다 (여기서 봇 계정이름의 끝은 대소문자 구별없이 ***bot***으로 끝나야 합니다)

봇 계정 설정이 끝나면 아래와 같은 형식의 토큰 값을 보내주는데 이 값을 복사해서 `알리미설정.ini` 파일의 `token` 항목에 붙여넣습니다

`110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw`

**그리고 본인이 새로 만든 봇을 검색해서 먼저 아무 말이나 대화를 걸어 줘야합니다**


# `알리미설정.ini` 설정 파일

```ini
[AlertConfig]
token = 
clientid = 
userlist = [일반] 알림목록.txt
userpriority = [속성] 알림목록.txt
sendthumbnail = True
refreshdelay = 30
refreshpriority = 10
newalertsonly = True
winnotify = True
```

#### `token` 텔레그램 봇 생성 후 받은 토큰

사용하지 않는 경우 비워두면 됩니다

```ini
token = 110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
```

#### `clientid` 텔레그램 클라이언트 아이디

필수 설정 사항은 아니며 설정하지 않은 경우 프로그램 실행시 자동으로 받아와 콘솔창에 아래와 같이 본인의 클라이언트 아이디를 출력해 줍니다

```ini
설정파일 로딩 완료!
[클라이언트 아이디]: 12345678
```

가끔씩 봇에게 말을 다시 걸어줘야 정상 작동하는 경우가 있는데 클라이언트 아이디를 직접 설정해주면 그런 현상이 사라집니다
```ini
clientid = 12345678
```

#### `userlist` 일반 알리미 유저 목록 파일 이름

해당 파일에 알림을 받을 스트리머의 로그인 아이디를 한줄에 한명씩 추가합니다

이 목록은 실시간으로 수정이 반영되므로 프로그램 실행중 언제든지 추가 및 삭제가 가능합니다
```ini
userlist = [일반] 알림목록.txt
```

알리미 실행 파일과 위치가 다를 경우 파일 전체 경로를 설정해주세요
```ini
userlist = C:\Users\cooluser\Desktop\직박구리\레전드.txt
```

#### `userpriority` 속성 알리미 유저 목록 파일 이름

해당 파일에 알림을 받을 스트리머의 로그인 아이디를 한줄에 한명씩 추가합니다

이 목록은 실시간으로 수정이 반영되므로 프로그램 실행중 언제든지 추가 및 삭제가 가능합니다
```ini
userpriority = [속성] 알림목록.txt
```

알리미 실행 파일과 위치가 다를 경우 파일 전체 경로를 설정해주세요
```ini
userpriority = C:\Users\cooluser\Desktop\찌르레기\전설.txt
```

#### `sendthumbnail` 썸네일 사용 여부

텔레그램 문자에 방송 썸네일을 같이 보내줍니다 (썸네일 평균 용량은 20-40kb 정도입니다)

속성 알림은 썸네일을 지원하지 않습니다

썸네일을 포함한 메시지를 전송합니다 
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

#### `refreshpriority` 갱신 대기 시간(초)

트위치 API를 통해 생방송 여부를 확인하고 다음 확인때까지 대기시간입니다

너무 짧은 딜레이는 서버에 부담을 주기때문에 10~20초 사이의 딜레이를 권장합니다

```ini
refreshpriority = 10
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

#### `winnotify` 윈도우 알림 여부

방송 시작시 윈도우 알림을 받습니다 (윈8 이상만 지원)

윈도우 알림 기능을 사용합니다
```ini
winnotify = True
```

윈도우 알림 기능을 사용하지 않습니다
```ini
winnotify = False
```

# `[일반] 알림목록.txt` 목록 파일

해당 파일에 일반 알림을 받을 아이디를 한줄에 하나씩 입력해 주세요

```
starcraft_kr
lck_korea
playoverwatch_kr
teaminven
```

# `[속성] 알림목록.txt` 목록 파일

해당 파일에 속성으로 알림을 받을 아이디를 한줄에 하나씩 입력해 주세요

```
zilioner
hanryang1125
noizemasta
kimpoong_official
01_84
```
