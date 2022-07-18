# 주식시장의 총 기록 데이터 ( 날짜, 시가, 종가, 고가, 저가, 볼륨량등 ) 을 데이터베이스 자동 구축


import pandas as pd
import pymysql
from datetime import datetime
from bs4 import BeautifulSoup
import requests
import json

class DBupdater:
    def __init__(self):
        '''생성자( 생성될때 ): mariaDB 연결 및 종목코드 딕셔너리 생성'''
        self.conn = pymysql.connect(host='####', port=####, db='####',
                                    user='####', passwd='####', charset='####', autocommit=True)# 로그인 정보


        with self.conn.cursor() as cur:

            sql ='''CREATE TABLE IF NOT EXISTS company_info (
	                    code VARCHAR(20),
	                    company VARCHAR(40),
	                    last_update_date DATE,
	                    PRIMARY KEY (code));''' # 회사 기본 정보

            cur.execute(sql) # sql로 실행

            sql ='''CREATE TABLE IF NOT EXISTS daily_price (
                        code VARCHAR(20),
                        date DATE,
                        open BIGINT(20),
                        high BIGINT(20),
                        low BIGINT(20),
                        close BIGINT(20),
                        diff BIGINT(20),
                        volume BIGINT(20),
                        PRIMARY KEY(code, date));;''' # 주가정보

            cur.execute(sql) # sql로 실행

        self.codes = dict() # 모든 상장법인 코드들이 담길 변수
        self.update_comp_info() # 함수호출


    def __del__(self):
        '''소멸자( 소멸할때 ) : 마리아DB 연결해제'''
        self.conn.close()

    def read_krx_code(self):
        '''KRX로부터 상장법인목록 파일을 읽어와서 데이터프레임으로 반환'''
        url = 'https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13'

        krx = pd.read_html(url, header=0)[0]
        krx = krx[['종목코드', '회사명']]
        krx = krx.rename(columns={'종목코드':'code', '회사명':'company'})
        krx.code = krx.code.map('{:06d}'.format) # 내용변경함수, 코드 6자리맞추고, 빈자리는 0으로

        return krx # -> update_comp_info

    def update_comp_info(self): # init에서 첫번쨰 실행 함수로 호출
        '''종목코드를 company_info 테이블에 업데이트한 후 딕셔너리에 저장'''
        sql = 'SELECT * FROM company_info'
        df = pd.read_sql(sql, self.conn) # sql 실행후 데이터 저장
        for idx in range(len(df)):
            self.codes[df['code'].values[idx]] = df['company'].values[idx] # 코드변수에 전체종목 저장

        with self.conn.cursor() as cur:
            sql = "SELECT max(last_update_date) FROM company_info"
            cur.execute(sql)
            rs = cur.fetchone()
            today_Date = datetime.today().strftime('%Y-%m-%d') # today를 불러오되, strftime으로 넣을것 지정

            # 초기상태 or 날짜상으로 업데이트 필요한지 확인구문
            # 마리아DB에 업뎃은 물론 codes 변수에도 업뎃
            if rs[0]==None or rs[0].strftime('%Y-%m-%d') < today_Date:
                krx = self.read_krx_code()
                for idx in range(len(krx)):
                    code = krx.code.values[idx]
                    company = krx.company.values[idx]
                    sql = f"REPLACE INTO company_info (code, company, last_update_date) VALUES ('{code}', '{company}', '{today_Date}')"
                    cur.execute(sql)
                    self.codes[code] = company
                    # sql에도 업뎃후 codes변수에도 업뎃

                    timenow = datetime.now().strftime('%Y-%m-%d %H:%M')
                    # cmd에 업뎃내용 출력문
                    print('{} {:04d} REPLACE INTO company_info VALUES {} {} {}'.format(timenow,idx,code,company,today_Date))
                print()


    def read_naver(self, code, company, pages_to_fetch):
        '''네이버금융에서 스크래핑후 데이터프레임으로 반환'''
        try:
            url= f"https://finance.naver.com/item/sise_day.nhn?code={code}"

            headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
                                     ' Chrome/98.0.4758.102 Safari/537.36'}

            url_text = requests.get(url, headers=headers)
            html = BeautifulSoup(url_text.text, 'lxml') # 파서는 lxml
            pgrr = html.find('td', class_='pgRR')
            if pgrr is None: # 예외 : not pgrr
                return None
            last_page = pgrr.a['href'].split('=')[-1] # 총페이지수

            df_main = pd.DataFrame() # 스크래핑한 데이터 값들이 저장될 변수

            pages = min(int(last_page), pages_to_fetch) # 전체페이지 up은 시간long, so json setting pages_to_fetch

            for page in range(1, pages + 1, 1):
                page_url = '{}&page={}'.format(url, page)
                page_url_text = requests.get(page_url, headers=headers)
                df_main = df_main.append(pd.read_html(requests.get(page_url, headers=headers).text)[0]) # 오류부분
                time_now = datetime.now().strftime('%Y-%m-%d %H:%M')
                print('[{}] [{}] - [{}] -> {} / {} pages are downloading...'.format(time_now,code,company,page,pages))

            df_main = df_main.rename(columns={'날짜':'Date','종가':'Close', '전일비':'Diff', '시가':'Open',
                                                  '고가':'High', '저가':'Low', '거래량':'Volume'})

            df_main['Date'] = df_main['Date'].replace('.','-')
            df_main = df_main.dropna() # Nan  값 삭제
            df_main[['Close', 'Diff', 'Open', 'High', 'Low', 'Volume']] = \
            df_main[['Close', 'Diff', 'Open', 'High', 'Low', 'Volume']].astype(int)
            # sql에서 bigint기 때문에 타입을 int로 전부 변경

            df_main = df_main[['Date', 'Open', 'High', 'Low', 'Close', 'Diff', 'Volume']]
            # sql 따라서 순서 변경

        except Exception as e:
            # 예외 발생 : 예외문장 출력, None을 반환
            print('Exception occurred : ', str(e))
            return None

        return df_main # 데이터프레임 리턴 -> update _daily_price



    def replace_info_db(self, df_main, num, code, company):
        '''read_naver -> DB에 replace 작업'''
        time_now = datetime.now().strftime('%Y-%m-%d %H:%M')
        with self.conn.cursor() as cur:
            for r in df_main.itertuples(): # 데이터프레임을 튜플로 바꿔줌
                sql = f"REPLACE INTO daily_price VALUES ('{code}', '{r.Date}', {r.Open}, {r.High}," \
                      f"{r.Low}, {r.Close}, {r.Diff}, {r.Volume})"
                # df_main프레임을 SQL 데이터베이스에 삽입 -> 중복된값이 있을경우, 추가하지않고 자동으로 값만 바꿔줌

                cur.execute(sql)
                print(f"[{time_now}] #{num +1} :  {code} - {company} Replace into DB [OK] ")


    def update_daily_price(self, pages_to_fetch):
        '''KRX 상장법인의 시세를 네이버로부터 읽어서 DB에 업데이트'''
        # update_dailt_price -> read_naver -> replace_into_db
        for idx, code in enumerate(self.codes): # 종목별로 순회처리
            df_main = self.read_naver(code, self.codes[code], pages_to_fetch)
            if df_main is None:
                continue
            self.replace_info_db(df_main, idx, code, self.codes[code])


    def execute(self):
        '''실행 함수 ( 원래는 매일 자동실행이 었는데, 그냥 내가 실행함수로 변경'''

        self.update_comp_info()

        try:
            with open('config.json', 'r') as in_file:
                config = json.load(in_file) # in_file의 내용을 불러와서 config에 넣는다.
                pages_to_fetch = config['pages_to_fetch'] # 값을 입력
        except  FileNotFoundError:
            with open('config.json', 'w') as out_file:
                pages_to_fetch = 100 # 초기설정
                config = {'pages_to_fetch': 1} # 두번쨰실행부터는 1로 변경
                json.dump(config, out_file) # 파일에 값을 넣는다.

        self.update_daily_price(pages_to_fetch)


if __name__=='__main__':
    db_up = DBupdater()
    db_up.execute()
    # db_up.read_krx_code()
