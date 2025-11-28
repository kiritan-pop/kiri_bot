# coding: utf-8
from functools import lru_cache
import requests
from bs4 import BeautifulSoup
import logging
logger = logging.getLogger(__name__)

KINRO_URL = "https://kinro.ntv.co.jp/lineup"
headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
el_date = '#after_lineup > div.list > ul > li:nth-child({i}) > div.cap > div.date'
el_title = '#after_lineup > div.list > ul > li:nth-child({i}) > div.cap > div.title > a'


@lru_cache(maxsize=4)
def get_kinro(date_str: str):
    movie_info = []

    try:
        res = requests.get(url=KINRO_URL,
                        headers=headers,
                        timeout=5)
        res.raise_for_status()  # HTTPエラーをチェック
        soup = BeautifulSoup(res.content, 'html.parser')
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"金ロー情報の取得に失敗しました: {e}")
        return movie_info  # エラー時は空のリストを返す
    except Exception as e:
        logger.warning(f"予期しないエラーが発生しました: {e}")
        return movie_info  # エラー時は空のリストを返す

    for i in range(6):
        try:
            tmp_date = soup.select(el_date.format(i=i+1))[0].text
            tmp_title = soup.select(el_title.format(i=i+1))[0].text
            movie_info.append((tmp_date, tmp_title))

        except IndexError:
            break

        except Exception as e:
            logger.debug(f"要素の取得に失敗しました (i={i+1}): {e}")

    return movie_info


if __name__ == '__main__':
    print(get_kinro())
