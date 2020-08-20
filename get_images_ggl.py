# coding: utf-8

import os
import json
import requests

count = 0

class GetImagesGGL:
    def __init__(self,key,engine_key):

        self.key = key
        self.engine_key = engine_key
        self.url = "https://www.googleapis.com/customsearch/v1"
        self.save_dir_path = "media/"

    def ImageSearch(self, search):
        url = f"{self.url}?key={self.key}&cx={self.engine_key}&searchType=image&cr=ja&num=10&safe=active&q={search}"
        rr=requests.get(url)
        unit_aa=json.loads(rr.text)
        # print(unit_aa)
        image_links = []
        for item in unit_aa['items']:
            image_links.append(item['link'])

        return image_links

    def get_images_forQ(self, term):
        make_dir(self.save_dir_path)
        url_list = []
        try:
            print('Searching images for: ', term)
            url_list = self.ImageSearch(term)
        except Exception as err:
            print(err)
            return []

        img_paths = []
        for url in url_list:
            try:
                img_path = make_img_path(self.save_dir_path, url, term)
                image = download_image(url)
                save_image(img_path, image)
                img_paths.append(img_path)
                print(f'saved image... {url}')
            except KeyboardInterrupt:
                break
            except ValueError:
                pass
            except Exception as err:
                print("%s" % (err))

        return img_paths

def make_dir(path):
    if not os.path.isdir(path):
        os.mkdir(path)

def make_img_path(save_dir_path, url, term):
    save_img_path = os.path.join(save_dir_path, term)
    make_dir(save_img_path)
    global count
    count += 1

    file_extension = os.path.splitext(url)[-1]
    if file_extension.lower() in ('.jpg', '.jpeg', '.gif', '.png', '.bmp'):
        full_path = os.path.join(save_img_path, str(count)+file_extension.lower())
        return full_path
    else:
        raise ValueError('Not applicable file extension')

def save_image(filename, image):
    with open(filename, "wb") as fout:
        fout.write(image)

def download_image(url, timeout=10):
    response = requests.get(url, allow_redirects=True, timeout=timeout)
    if response.status_code != 200:
        error = Exception("HTTP status: " + response.status_code)
        raise error

    content_type = response.headers["content-type"]
    if 'image' not in content_type:
        error = Exception("Content-Type: " + content_type)
        raise error

    return response.content
