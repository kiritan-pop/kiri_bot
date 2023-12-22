# coding: utf-8
from functools import lru_cache
import requests
from bs4 import BeautifulSoup
import logging
logger = logging.getLogger(__name__)

KINRO_URL = "https://kinro.ntv.co.jp/"

selector_list = [
    (
        'next',
        '#next > div.mds > time',
        '#next > div.photo.imgfit > a:nth-child(1) > p'
        ),
    (
        'after',
        '#after_lineup > div.list > ul > li:nth-child({i}) > div.cap > div.date',
        '#after_lineup > div.list > ul > li:nth-child({i}) > div.cap > div.title > a'
        )
    ]


@lru_cache(maxsize=4)
def get_kinro(date_str: str):
    movie_info = []

    headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        res = requests.get(url=KINRO_URL,
                        headers=headers,
                        timeout=5)
        soup = BeautifulSoup(res.content)
        
    except Exception as e:
        logger.error(e, exc_info=True)

    for ptn, el_date, el_title in selector_list:
        try:
            if ptn == 'next':
                tmp_date = soup.select(el_date)[0].text
                tmp_title = soup.select(el_title)[0].text
                movie_info.append((tmp_date, tmp_title))
            elif ptn == 'after':
                for i in range(5):
                    tmp_date = soup.select(el_date.format(i=i+1))[0].text
                    tmp_title = soup.select(el_title.format(i=i+1))[0].text
                    movie_info.append((tmp_date, tmp_title))

        except Exception as e:
            logger.error(e, exc_info=True)

    return movie_info


if __name__ == '__main__':
    print(get_kinro())
