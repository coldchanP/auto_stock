# 크레온 자동 로그인

from pywinauto import application
import os, time
import ctypes # c 자료형 사용 및 DLL 호출
import win32com.client # for Com obbject of CReon API

# creon plus 공통 object
cpstatus = win32com.client.Dispatch('CpUtil.CpCybos') # 시스템 상태 정보
cptraderutil = win32com.client.Dispatch('CpTrade.CpTdUtil') # 주문관련 도구


def creon_connect():

    os.system('taskkill /IM coStarter* /F /T') # taskill co , cp ,dib -> 크레온 관련 프로세스
    os.system('taskkill /IM CpStart* /F /T') # /F 강제 /T 종료
    os.system('taskkill /IM DibServer* /F /T') # 크레온 미실행시 오류발생 -> 무시가능
    os.system('wmic process where "name like \'%coStarter%\'" call terminate') # 한번더 강제종료
    os.system('wmic process where "name like \'%CpStar%\'" call terminate')
    os.system('wmic process where "name like \'%DibServer%\'" call terminate')
    time.sleep(10)

    app = application.Application()
    app.start('C:\CREON\STARTER\coStarter.exe /prj:cp /id:gog6012 /pwd:gkvhs12! /pwdcert:qkrtjdcks1028! /autostart')
    # 앱 시작 경로/id/비번/공인비번/autostart # cp는 크레온 플러스를 의미, c 가 일반 hts
    time.sleep(35)


def check_creon_sys():
    '''크레온 플러스 시스템 점검 함수'''

    # 관리자 권한으로 프로세스 실행 여부
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print('check_creon_sys() : admin user -> FAILED')
        return False

    # 크레온 연결여부
    if (cpstatus.IsConnect == 0):
        print('chek_creon_sys() : Creon Connect error')
        return False

    # 주문관련 초기화
    if (cptraderutil.TradeInit(0) != 0):
        print('check_creon_sys() : init Trade -> FAILED')
        return False

    print('Creon Connect Success')
    return True




