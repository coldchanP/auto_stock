# 상폐위기 / 오류를 불러일으키는 종목을 삭제하는 기능

import requests
from bs4 import BeautifulSoup
import pymysql
import pandas as pd


maria_conn = pymysql.connect(host='####', port=####, db='####',
                            user='####', passwd='####', charset='####', autocommit=True)  # 로그인 정보

lst = [] # 코드만 넣을 리스트
cnt = 0
cnt2 = 0
sql = 'SELECT * FROM company_info'
df = pd.read_sql(sql,maria_conn)
for idx in range(len(df)): # 리스트에 코드 추가
    lst.append(df['code'].values[idx])

for code in lst:
    try:
        print('현재 코드 : {} '.format(code))
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        url_text = requests.get(url,headers=0)
        html = BeautifulSoup(url_text.text, 'lxml')
        searh = html.find('img', class_='kospi') or html.find('img', class_='kosdaq')
        if searh['alt'] == '코넥스':
            print('코넥스 발견  -> 삭제합니다.')
            with maria_conn.cursor() as cur:
                sql_del = f"DELETE FROM company_info WHERE code={code}"
                cur.execute(sql_del)
            cnt += 1
    except TypeError:
        print('상폐추정/오류를 불러 일으키는 종목 -> 삭제합니다')
        with maria_conn.cursor() as cur:
            sql_del = f"DELETE FROM company_info WHERE code={code}"
            cur.execute(sql_del)
        cnt2 += 1

print('삭제된 코넥스 갯수 : {}   /   except(상폐/오류) 갯수는 : {}'.format(cnt,cnt2))
