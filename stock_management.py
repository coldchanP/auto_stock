# 관리종목/ 거래정지종목 스크래핑

from selenium import webdriver # etf 페이지 스크래핑에 필요
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup


class manage_stock():
    def __init__(self):
        # 크롬드라이버를 사용해서 스크래핑 해야해서, 드라이버 셋팅
        self.opt = webdriver.ChromeOptions()
        self.opt.add_argument('headless')
        self.drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=self.opt)
        self.drv.implicitly_wait(5)
        self.code = []
        self.manage1()

    def __del__(self):
        self.drv.close()

    def manage1(self): # 관리종목 스크래핑
        self.drv.get('https://finance.naver.com/sise/management.naver')
        # 부티풀 수프로 테이블을 스크레핑
        bs = BeautifulSoup(self.drv.page_source, 'lxml')
        table = bs.find_all("a", class_="tltle")

        for td in table:
            s = str(td['href']).split('=')
            self.code.append(s[-1])

        self.manage2()

    def manage2(self): # 거래정지 종목 스크래핑
        self.drv.get('https://finance.naver.com/sise/trading_halt.naver')

        # 부티풀 수프로 테이블을 스크레핑
        bs = BeautifulSoup(self.drv.page_source, 'lxml')
        table = bs.find_all("a", class_="tltle")

        for td in table:
            s = str(td['href']).split('=')
            if s not in self.code:
                self.code.append(s[-1])

if __name__ == '__main__':
    start = manage_stock()
