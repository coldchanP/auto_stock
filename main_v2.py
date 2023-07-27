# 주식 자동 매매 프로그램 구현 메인문 -> 단기스윙용 ( 7일 )



from pywinauto import application
import win32com.client
import requests
from datetime import datetime
from datetime import timedelta
import pymysql
import time
import pandas as pd
import random

import auto_connect
from DB_search import DB_search  # DB_차트 조회용
import stock_management

class auto_stock():
    def __init__(self):

        # 크레온 연결
        auto_connect.creon_connect()
        if auto_connect.check_creon_sys() == False:
            print('크레온 연결 실패 확인 바랍니다.')

        # 마리아 디비 연결정보
        self.maria_conn = pymysql.connect(host='localhost', port=3306, db='####',
                                          user='root', passwd='####', charset='utf8', autocommit=True)  # 로그인 정보

        # 크레온 관련
        self.cptradeutil = win32com.client.Dispatch('CpTrade.CpTdUtil')  # 주문관련도구
        self.cpbalance = win32com.client.Dispatch('CpTrade.CpTd6033')  # 계좌정보 ( 수익률도 이쪽 )
        self.cpcodemgr = win32com.client.Dispatch('CpUtil.CpStockCode')  # 종목코드
        self.cporder = win32com.client.Dispatch('CpTrade.CpTd0311')  # 주식 주문
        self.cpstock = win32com.client.Dispatch('Dscbo1.StockMst')  # 현재값 받기
        # 슬랙 토큰
        self.myToken = "토큰명"  # 슬랙 토큰

        self.target_codes = dict()
        self.DB_data = DB_search()  # DB데이터를 불러올 함수 ( 직접 구현 )
        self.codes = {}
        self.target = [] # 타겟 전체의 집합
        self.target_lst = {} # dict[타겟] = 매수 수량  // 이저장된 딕셔너리


        self.total_qty = 6 # 매수할 종목갯수
        self.money = 300000 # 한종목당  한도 정해놓음

    def __dell__(self):
        '''소멸자 : 마리아 디비 연결해제'''
        self.maria_conn.close()

    def check_sql_or_buy(self):
        '''현재 매수중인 데이터가 있는지 확인하는 함수'''
        self.cptradeutil.TradeInit()
        self.acc = self.cptradeutil.AccountNumber[0]  # 계좌번호
        self.accflag = self.cptradeutil.GoodsList(self.acc, 1)  # -1: 전체, 1: 주식, 2: 선물/옵션  -> 굿즈리스트
        self.cpbalance.SetInputValue(0, self.acc)  # 계좌번호
        self.cpbalance.SetInputValue(1, self.accflag[0])  # 상품구분 - 주식 상품 중 첫번쨰
        self.cpbalance.SetInputValue(2, 50)  # 요청 건수 ( 최대 50 )
        self.cpbalance.BlockRequest()

        ######## 매수중인것이 있다면 #############
        check_buying_qty = int(self.cpbalance.GetHeaderValue(7))
        if check_buying_qty != 0:  # 계좌 보유 종목수 확인후 주식 매수후 보유중이면
            if self.total_qty - check_buying_qty > 0:  # 5종목이 매수중이 아니면
                print('종목의 수가 self.total_qty개가 아니므로, 부족한 갯수만큼 매수후 매도진행합니다.')
                print('하지만 관망모드가 존재하므로 1을 입력할시 매수진행 하지않고 매도모드로 넘어갑니다.')
                i = int(input('관망모드 : 1 // 자동모드 : 2 : '))
                if i == 2:
                    self.buy_to_stock(self.total_qty-check_buying_qty) # 부족한 갯수만큼 qty로 넘겨줌
                elif i == 1:
                    self.selling_checking()
            else:
                print('주식 보유중.. 매도대기로 들어갑니다.')
                self.selling_checking()

        ######### 매수중인것이 없다면 ##############
        elif check_buying_qty == 0:  # 매수 대기
            print('종목이 비었습니다. 매수 대기로 들어갑니다')
            self.buy_to_stock(self.total_qty)  # 매수할 종목 선정 및 타켓 sql 초기화

    def selling_checking(self):
        '''매도 조건을 충족하는게 확인되면 시장가로 매도하는 함수'''

        init_Check = self.cptradeutil.TradeInit(0)  # 주문 초기화

        if (init_Check != 0):
            print("주문 초기화 실패")
            exit()

        ### sql에서 매수/타켓/로스 코드 불러오기
        sql = 'SELECT * FROM target'
        df = pd.read_sql(sql, self.maria_conn)  # sql 실행후 데이터 저장
        target_dict = {} # 타겟값 딕셔너리
        target_dict2 = {} # 수익률 계산용 딕셔너리
        target_dict3 = {} # 로스 계산용 딕셔너리
        for idx in range(len(df)):
            target_dict[df['code'].values[idx]] = df['target_price'].values[idx]
            target_dict2[df['code'].values[idx]] = df['buy_price'].values[idx]
            target_dict3[df['code'].values[idx]] = df['loss_price'].values[idx]
        #################################



        print('매도를 시작합니다. 시간이 오래소요될 예정입니다.')
        while (self.cpbalance.GetHeaderValue(7)):  # 보유중인 종목이 팔릴때까지 while
            #### 15시 20분 강제종료를 위한 시간문 ###
            t_now = datetime.now()
            t_exit = t_now.replace(hour=15, minute=20, second=0, microsecond=0)
            if t_now > t_exit: # 15시 20분 강제종료
                print('시간이 15시 20분이 넘어 주식장이 종료되었으니 프로그램을 종료합니다.')
                break
            ####################################

            lst_ = list(target_dict)
            for idx, i in enumerate(lst_):  # 보유중인 종목수만큼 for 돌면서 관리
                time.sleep(10)
                self.cpstock.SetInputValue(0, str('A' + i))
                self.cpstock.BlockRequest()
                print('실시간 감시중....')
                print('--------------------------------')
                print(f"현재 종목 : {i}  - 현재가 / 목표가 : {self.cpstock.GetHeaderValue(11)} / {int(target_dict[i])} ")
                print('현재 수익률 : {:0.2f} '.format((int(self.cpstock.GetHeaderValue(11)) - target_dict2[i])
                                                 / target_dict2[i] * 100))
                print('--------------------------------')

                # 손익, 손절가 매도
                if int(self.cpstock.GetHeaderValue(11)) >= int(target_dict[i]) or \
                        int(self.cpstock.GetHeaderValue(11)) <= int(target_dict3[i]):  # 현재값 > 목표가 or 현재값 < 손절가


                    # 매도
                    self.cporder.SetInputValue(0, "1")  # 1: 매도
                    self.cporder.SetInputValue(1, self.acc)  # 계좌번호
                    self.cporder.SetInputValue(2, self.accflag[0])  # 주식 상품중 첫번째
                    self.cporder.SetInputValue(3, str('A' + i))  # 종목 코드
                    self.cporder.SetInputValue(4, df['qty'].values[idx])  # 매도 수량
                    self.cporder.SetInputValue(7, "0")  # 조건 0:없음
                    self.cporder.SetInputValue(8, "03")  # 시장가매도
                    request_stock = self.cporder.BlockRequest()  # 매도 주문 request

                    if (request_stock != 0):  # 주문요청 확인
                        print("주문요청 오류", request_stock)
                        # 0: 정상,  그 외 오류, 4: 주문요청제한 개수 초과
                        exit()

                    text = f"'{i}' : '{df['qty'].values[idx]}'주 시장가 매도주문 요청 / 체결확인바람 "
                    with self.maria_conn.cursor() as cur:
                        sql = f"DELETE FROM target WHERE code={i}"
                        cur.execute(sql)
                    print('데이터베이스에서 매도한 종목 삭제완료')
                    self.log_message(self.myToken, '#project', text)  # 매도 요청후 슬랙로그발생
                    del target_dict[i]  # 매도 완료된 종목은 pop
                    del target_dict2[i] # 매도 완료된 종목은 pop
                    del target_dict3[i] # 매도 완료된 종목은 pop

                    time.sleep(0.7)

        if self.cpbalance.GetHeaderValue(7) == 0:
            text = " 매도가 전부 체결되었습니다. 프로그램을 종료합니다. "
            self.log_message(self.myToken, '#project', text)  # 올매도 / 프로그램종료 선언

        # 프로그램 종료

    def buy_to_stock(self, qty):
        # '''매수하는 함수'''


        init_Check = self.cptradeutil.TradeInit(0)  # 주문 초기화

        if (init_Check != 0):
            print("주문 초기화 실패")
            exit()

        self.checking_for_target(qty)  # 먼저 타켓 모아옴
        print(self.target_lst)

        print('타켓이 정해졌습니다. / 장이 시작되었습니다. 매수 시작합니다.!!')
        # 매수
        for code in self.target_lst:
            self.cporder.SetInputValue(0, "2")  # 2: 매수
            self.cporder.SetInputValue(1, self.acc)  # 계좌번호
            self.cporder.SetInputValue(2, self.accflag[0])  # 주식 상품중 첫번째
            self.cporder.SetInputValue(3, str('A' + code))  # 종목 코드
            self.cporder.SetInputValue(4, self.target_lst[code])  # 매수 수량
            self.cporder.SetInputValue(7, "0")  # 조건 0:없음
            self.cporder.SetInputValue(8, "03")  # 시장가매수
            request_stock = self.cporder.BlockRequest()  # 매수 주문 요청

            if (request_stock != 0):  # 주문요청 확인
                print("주문요청 오류", request_stock)
                # 0: 정상,  그 외 오류, 4: 주문요청제한 개수 초과
                exit()

            text = f"{code} : {self.target_lst[code]}주 시장가 매수주문 요청 / 체결확인바람 "
            self.log_message(self.myToken, '#project', text)  # 매수 요청후 슬랙로그발생
            time.sleep(0.7)

        # 매수후 매도대기모드로 들어감
        time.sleep(10)
        self.selling_checking()



    def checking_for_target(self, qty):
        ''' 매수할 종목 선정 및 타켓 sql 초기화'''
        # 1 MFI, 2 볼린저밴드, macd가 시그널 하향돌파 -> 매수포인트 데이터는 4달치

        manage = stock_management.manage_stock() # 관리, 거래정지 종목 리스트
        danger_stock = manage.code


        print('타켓 확인모드에 진입하였습니다. 타켓을 선택합니다.')

        # DB_search에서 종목-코드 정보 읽어와서 codes에 저장
        sql = 'SELECT * FROM company_info'  # sql에 저장되어 있는 코드,종목명 불러와서 codes에 저장
        df = pd.read_sql(sql, self.maria_conn)
        end_time = datetime.now().strftime('%Y-%m-%d')  # 조회 종료일
        for idx in range(len(df)):
            self.codes[df['code'].values[idx]] = df['company'].values[idx]

        # tartget - sql 초기화 :
        if qty == 5: # if all new buy
            with self.maria_conn.cursor() as cur:
                sql = 'DELETE FROM target'
                cur.execute(sql)

        # 메인 비교 구문 # 메인 종목 선정구문!
        for idx, code in enumerate(self.codes):
            if '스팩' in self.codes[code] or code in danger_stock: # 스팩주/관리종목/상페종목은 제외위함
                continue

            df = self.DB_data.get_daily_price(code)
            try:
                # MFI : 30 70 설정
                df['TP'] = (df['high'] + df['low'] + df['close']) / 3  # 중심값 구하기
                df['PMF'] = 0  # 긍정적 흐름지표
                df['NMF'] = 0  # 부정적 흐름지표
                for i in range(len(df) - 1):  # 다음날의 값이랑 오늘의 값이랑 비교
                    if df.TP.values[i] < df.TP.values[i + 1]:
                        df.PMF.values[i + 1] = df.TP.values[i + 1] * df.volume.values[i + 1]
                        df.NMF.values[i + 1] = 0
                    else:
                        df.NMF.values[i + 1] = df.TP.values[i + 1] * df.volume.values[i + 1]
                        df.PMF.values[i + 1] = 0
                df['MFR'] = df.PMF.rolling(window=14).sum() / df.NMF.rolling(window=14).sum()
                df['MFI10'] = 100 - (100 / (1 + df['MFR']))

                # 볼린저밴드 : 중간선 밑에 기준

                df['MA20'] = df['close'].rolling(window=20).mean()  # 20일선 and 중간볼린저밴드 = 20일간의 평균금액
                df['stddev'] = df['close'].rolling(window=20).std()  # 20일의 표준편차 구하기 std함수 사용
                df['upper'] = df['MA20'] + (df['stddev'] * 2)  # 상단볼린저밴드  = 중간볼린저밴드 + (표준편차 * 2)
                df['lower'] = df['MA20'] - (df['stddev'] * 2)  # 하단볼린저밴드 = 중간볼린저밴드 - (표준편차 * 2)
                df['perb'] = (df['close'] - df['lower']) / (df['upper'] - df['lower']) * 100

                # MACD : 시그널선 하향돌파 매수

                df['ema60'] = df.close.ewm(span=60).mean()  # 종가기준 12주 지수 이동평균
                df['ema130'] = df.close.ewm(span=130).mean()  # 종가기준 26주 지수 이동평균
                df['MACD'] = df.ema60 - df.ema130  # 12주 이평균 - 26주 이평균 = MACD
                df['MACD_signal'] = df.MACD.ewm(span=45).mean()  # MACD 시그널선 = MACD의 9주 이동평균

                if df.iloc[-1].MFI10 < 30 and (1000 < df.iloc[-1].close < 100000):  # 조건 만족하면 sql에 추가
                    if (df.iloc[-1].close > df.iloc[-1].lower) and (df.iloc[-1].close < df.iloc[-1].MA20):
                        print('타켓 발견')
                        self.target.append(code)  # 타켓 리스트에 입력

                    elif df.iloc[-1].MACD < df.iloc[-1].MACD_signal:
                        print('타켓 발견')
                        self.target.append(code)  # 타켓 리스트에 입력

            except IndexError:  # 상장한지 얼마 안된기업들은 index오류 발생해 except 지정
                print(f"{idx}번쨰 {code}는 index오류로 배제합니다.")

        print('타켓이 모두 선택 되었습니다.')



        # sql - 타켓에 있는 종목은 매수 금지리스트를 위한 준비문 ###########
        sql = 'SELECT * FROM target'
        df = pd.read_sql(sql, self.maria_conn)  # sql 실행후 데이터 저장
        checking_for_lst = []
        for idx in range(len(df)):
            checking_for_lst.append([df['code'].values[idx]])
        #####################################################################


        #### 9시1분에 랜덤타겟 선별하여 매수로 넘기는 시간문 -> 즉 미리 켜놓고 대기하려고 ###
        t_now = datetime.now()
        t_start = t_now.replace(hour=9, minute=1, second=0, microsecond=0)
        while datetime.now() < t_start:  # 9시 1분에 매수로직이 시작
            print('랜덤타겟셋에서 대기중 !!!  9시전이라 대기중입니다.. ')
            time.sleep(10)
        ##################



        if len(self.target) > 5:
            print('랜덤타겟 선별중........')
            while (len(self.target_lst) < qty):  # 5개를 채울때 까지 while문
                rand = random.randrange(0, len(self.target))
                if self.target[rand] in checking_for_lst: # 난수로 생성한 타켓이 이미 sql 등록되어있으면 continue
                    continue

                self.cpstock.SetInputValue(0, str('A' + self.target[rand]))
                self.cpstock.BlockRequest()
                stock_qty = self.money // int(self.cpstock.GetHeaderValue(11))
                self.target_lst[self.target[rand]] = stock_qty
                target_price = self.cpstock.GetHeaderValue(11) * 1.036  # 매도목표가
                loss_price = self.cpstock.GetHeaderValue(11) * 0.968 # 손절가
                time.sleep(2)

                with self.maria_conn.cursor() as cur:
                    sql = f"INSERT INTO target (code,company,buy_price,target_price,loss_price,qty,date) VALUES" \
                          f"('{self.target[rand]}','{self.codes[self.target[rand]]}','{self.cpstock.GetHeaderValue(11)}'," \
                          f"'{target_price}','{loss_price}','{stock_qty}','{end_time}')"
                    cur.execute(sql)


        else: # 타켓이 5개 이하로 생길경우 -> 사실상 희박한 확률 -> 코드 수정 x
            for i in range(len(self.target)):
                if self.target[i] in checking_for_lst: # 난수로 생성한 타켓이 이미 sql 등록되어있으면 continue
                    continue
                self.cpstock.SetInputValue(0, str('A' + self.target[i]))
                self.cpstock.BlockRequest()
                stock_qty = self.money // int(self.cpstock.GetHeaderValue(11))
                self.target_lst[self.target[i]] = stock_qty
                target_price = self.cpstock.GetHeaderValue(11) * 1.036  # 매도목표가
                loss_price = self.cpstock.GetHeaderValue(11) * 0.968 # 손절가
                time.sleep(2)

                with self.maria_conn.cursor() as cur:
                    sql = f"INSERT INTO target (code,company,buy_price,target_price,loss_price,qty,date) VALUES" \
                          f"('{self.target[i]}','{self.codes[self.target[i]]}','{self.cpstock.GetHeaderValue(11)}'," \
                          f"'{target_price}','{loss_price}','{stock_qty}','{end_time}')"
                    cur.execute(sql)





    def log_message(self, token, channel, text):
        '''log_message(myToken, "채팅방", '메세지') 메시지 양식
           로그 메세지 출력 및 슬랙으로도 로그메세지 출력'''
        time_now = datetime.now().strftime('[%m/%d %H:%M:%S]')
        response = requests.post("https://slack.com/api/chat.postMessage",
                                 headers={"Authorization": "Bearer " + token},
                                 data={"channel": channel, "text": time_now + '\n' + text}
                                 )

        result = response.text.split(',')
        if 'true' in result[0]:  # 슬랙출력확인 되면 로그 출력
            print('슬랙로그출력')
        else:
            print('슬랙 로그 미출력 -> 오류발생')
        print(time_now, text)

    def start_program(self):
        ''' 시작 함수'''
        self.check_sql_or_buy()
        print('......프로그램 종료중.......')
        print('........................')


if __name__ == '__main__':
    start = auto_stock()
    start.start_program()






