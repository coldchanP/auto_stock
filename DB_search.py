# 데이터베이스에 저장된 종목들의 일별 시세 조회 API


import pandas as pd
import pymysql
from datetime import datetime
from datetime import timedelta
import re


class DB_search:
    def __init__(self):
        '''데이터 베이스 연결 및 종목코드 dic 생성'''
        self.conn = pymysql.connect(host='####', user='####', passwd='####',port=####,
                                    db='####',charset='utf8', autocommit=True)
        self.codes = {}
        self.get_company_info() # -> 함수를 호출해 회사 정보 불러오기.

    def __del__(self):
        """데이터베이스 연결해제"""
        self.conn.close() # mariada exit

    def get_company_info(self):
        '''DB에서 읽어와서 codes에 저장'''
        sql = 'SELECT * FROM company_info'
        df = pd.read_sql(sql, self.conn)  # sql 실행후 데이터 저장
        for idx in range(len(df)):
            self.codes[df['code'].values[idx]] = df['company'].values[idx]

    def get_daily_price(self,code, start_date = None, end_date= None):
        '''종목별 시세를 데이터프레임 형태로 반환해 최종리턴 -> cmd에서 사용될 함수
            - CODE             : KRX 종목코드 또는 상장기업명
            - START_DATE       : 조회시작일 (0000-00-00)
            - END_ DATE        : 조회종료일 (0000-00-00)
            - 날짜는 미입력시 자동으로 START = 1년전 오늘, END = 오늘
            '''

        if start_date is None:
            time_set = datetime.today() - timedelta(days=150) # 오늘 날짜로부터 1년전 을 start로 정함
            start_date = time_set.strftime('%Y-%m-%d')
        else: # 입력되었는데, 정상적인 형태로 년월일을 표시안했을 경우를 대비한.
            start_lst = re.split('\D+', start_date) # \D+는 숫자가아닌 문자들로 이루어진 문자열
            if (start_lst[0] == ' '):
                start_lst = start_lst[1:]

            s_year = int(start_lst[0])
            s_month = int(start_lst[1])
            s_day = int(start_lst[2])
            start_date = f"{s_year:04d}-{s_month:02d}-{s_day:02d}"

        if end_date is None:
            end_date = datetime.today().strftime('%Y-%m-%d')
        else: # 입력되었는데, 정상적인 형태로 년월일을 표시안했을 경우를 대비한.
            end_lst = re.split('\D+', end_date) # \D+는 숫자가아닌 문자들로 이루어진 문자열
            if (end_lst[0] == ' '):
                end_lst = end_lst[1:]
            e_year = int(end_lst[0])
            e_month = int(end_lst[1])
            e_day = int(end_lst[2])
            end_date = f"{e_year:04d}-{e_month:02d}-{e_day:02d}"

        codes_key = list(self.codes.keys())
        codes_val = list(self.codes.values())

        if code in codes_key:
            pass
        elif code in codes_val:
            code_index = codes_val.index(code)
            code = codes_key[code_index]
        else:
            print('code_value ERROR')

        sql = f"SELECT * FROM daily_price WHERE code = '{code}' and date >= '{start_date}' and date <= '{end_date}'"
        df_main = pd.read_sql(sql, self.conn) # sql로부터 데이터프레임까지
        # df_main = df_main.sort_values(by='date', ascending=False) # 내림차순으로 설정
        df_main.index = df_main['date'] # 인덱스를 날짜로

        return df_main

