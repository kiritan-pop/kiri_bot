# coding: utf-8

import os
import json
import requests

# きりぼコンフィグ
from kiribo.config import MEDIA_PATH
from kiribo import util
logger = util.setup_logger(__name__)

class GetImagesGGL:
    def __init__(self,key,engine_key):
        self.count = 0
        self.key = key
        self.engine_key = engine_key
        self.url = "https://www.googleapis.com/customsearch/v1"
        self.save_dir_path = "media/"

    def ImageSearch(self, search):
        url = f"{self.url}?key={self.key}&cx={self.engine_key}&searchType=image&q={search}"
        rr = requests.get(url)
        unit_aa=json.loads(rr.text)
        image_links = []
        for item in unit_aa['items']:
            image_links.append(item['link'])

        return image_links

    def get_images_forQ(self, term):
        url_list = []
        try:
            logger.info(f'Searching images for: {term}')
            url_list = self.ImageSearch(term)
        except Exception as err:
            logger.error(err)
            return []

        img_paths = []
        for url in url_list:
            try:
                img_paths.append(util.download_media(url, subdir=term))
            except KeyboardInterrupt:
                break
            except ValueError:
                pass
            except Exception as err:
                logger.error(err)

        return [a for a in img_paths if a]
