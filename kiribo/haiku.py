# coding: utf-8

import MeCab
import re, os
import jaconv
import itertools
from PIL import Image, ImageFont, ImageDraw

from kiribo.config import IPADIC_PATH, KIGO_PATH, FONT_PATH_IKKU, MEDIA_PATH
from kiribo import  util

logger = util.setup_logger(__name__)


def make_ikku_image(song, avatar_static):
    frame_img = Image.open('./data/ikku_frame.png').convert("RGBA")

    avatar_static_img_path = util.download_media(avatar_static)
    img_clear = Image.new("RGBA", frame_img.size, (255, 255, 255, 0))
    # アイコン
    if avatar_static_img_path:
        avatar_static_img = Image.open(avatar_static_img_path).convert("RGBA")
        max_size = max(avatar_static_img.width, avatar_static_img.height)
        RS_SIZE = 120
        avatar_static_img = avatar_static_img.resize(
            (avatar_static_img.width*RS_SIZE//max_size, avatar_static_img.height*RS_SIZE//max_size), resample=Image.LANCZOS)
        img_clear.paste(avatar_static_img, (frame_img.width -
                                            RS_SIZE - 40, frame_img.height - RS_SIZE - 40))

    # 文字追加
    FONT_SIZE = 48
    font = ImageFont.truetype(
        FONT_PATH_IKKU, size=FONT_SIZE, layout_engine=ImageFont.LAYOUT_RAQM)
    draw = ImageDraw.Draw(img_clear)
    for index, phrase in enumerate(song.phrases):

        draw.text((img_clear.width - (FONT_SIZE+16) * (index+1) - 36, FONT_SIZE*index*(index + 1) + 128),
                  "".join([node.surface for node in phrase]),
                  fill=(20, 20, 20), font=font, direction="ttb")

    frame_img = Image.alpha_composite(frame_img, img_clear)
    save_path = os.path.join(MEDIA_PATH, "ikku_tmp.png")
    frame_img.save(save_path)
    return save_path


class Reviewer():
    def __init__(self, rule=None):
        self.rule = rule
        self.parser = Parser()

    def find(self, text):
        nodes = self.parser.parse(text)
        for index in range(len(nodes)):
            song = SongWithSeasonWord(nodes[index:], rule=self.rule)
            if song.is_valid():
                return song

    def find_just(self, text):
        song = SongWithSeasonWord(self.parser.parse(text), exactly=True, rule=self.rule)
        if song.is_valid():
            return song

    def judge(self, text):
        return SongWithSeasonWord(self.parser.parse(text), exactly=True, rule=self.rule).is_valid()

    def search(self, text):
        nodes = self.parser.parse(text)
        return [song for song in [SongWithSeasonWord(nodes[index:], rule=self.rule) for index in range(len(nodes))] if song.is_valid()]


class Song():
    DEFAULT_RULE = [5, 7, 5]

    def __init__(self, nodes, exactly=False, rule=None):
        self.exactly = exactly
        self.rule = rule or Song.DEFAULT_RULE
        self.phrases = Scanner(exactly=self.exactly,
                            nodes=nodes, rule=self.rule).scan() or []
        self.nodes = list(itertools.chain.from_iterable(self.phrases))
        self.surfaces = [node.surface for node in self.nodes]
        self.bracket_state = BracketState(self.surfaces)

    def is_valid(self):
        if self.phrases == []:
            return False
        elif self.bracket_state.is_odd():
            return False
        else:
            return True


class SongWithSeasonWord(Song):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.season_words = [l.strip() for l in open(KIGO_PATH).readlines()]
        self.season_word = None
        for surface in self.surfaces:
            if surface.strip() in self.season_words:
                self.season_word = surface.strip()

    def is_haiku(self):
        return not self.is_senryu()

    def is_senryu(self):
        return self.season_word == None


class Parser():
    def __init__(self):
        self.mecab = MeCab.Tagger(f"-d {IPADIC_PATH}")

    def parse(self, text):
        mecab_node = self.mecab.parseToNode(text)
        node_list = []
        while mecab_node:
            node = Node(mecab_node)
            if node.is_analyzable():
                node_list.append(node)
            mecab_node = mecab_node.next
        [logger.debug(f"{node.surface},{node.type},{node.subtype1},{node.subtype2},{node.subtype3},{node.subtype3},{node.conjugation1},{node.conjugation2},{node.root_form},{node.pronunciation_mora}")
            for node in node_list]
        return node_list


class Node():
    STAT_ID_FOR_NORMAL = 0
    STAT_ID_FOR_UNKNOWN = 1
    STAT_ID_FOR_BOS = 2
    STAT_ID_FOR_EOS = 3

    # @param node [Natto::MeCabNode]
    def __init__(self, node):
        self.stat = node.stat
        self.surface = node.surface
        self.feature = node.feature.split(",")
        self.type = self.feature[0]
        self.subtype1 = self.feature[1]
        self.subtype2 = self.feature[2]
        self.subtype3 = self.feature[3]
        self.conjugation1 = self.feature[4]
        self.conjugation2 = self.feature[5]
        self.root_form = self.feature[6]
        self.pronunciation = self.feature[8] if len(self.feature) >= 9 else ""
        self.pronunciation_mora = re.sub(
            r'[^アイウエオカ-モヤユヨラ-ロワヲンヴー]', '', jaconv.hira2kata(self.pronunciation))
        self.pronunciation_length = len(self.pronunciation_mora)

    def is_analyzable(self):
        return self.stat not in (Node.STAT_ID_FOR_BOS, Node.STAT_ID_FOR_EOS)

    def is_element_of_ikku(self):
        return self.stat == Node.STAT_ID_FOR_NORMAL

    def is_first_of_ikku(self):
        if not self.is_first_of_phrase():
            return False
        elif self.type == "記号" and self.subtype1 not in ["括弧開", "括弧閉"]:
            return False
        else:
            return True

    def is_first_of_phrase(self):
        if self.type in ["助詞", "助動詞"]:
            return False
        elif self.subtype1 in ["非自立", "接尾"]:
            return False
        elif self.subtype1 == "自立" and self.root_form in ["する", "できる"]:
            return False
        else:
            return True

    def is_last_of_ikku(self):
        if self.type in ["名詞接続", "格助詞", "係助詞", "連体化", "接続助詞", "並立助詞", "副詞化", "数接続", "連体詞"]:
            return False
        elif self.conjugation2 == "連用タ接続":
            return False
        elif self.conjugation1 == "サ変・スル" and self.conjugation2 == "連用形":
            return False
        elif self.type == "動詞" and self.conjugation2 in ["仮定形", "未然形"]:
            return False
        elif self.type == "名詞" and self.subtype1 == "非自立" and self.pronunciation == "ン":
            return False
        else:
            return True

    def is_last_of_phrase(self):
        return self.type != "接頭詞"


class BracketState():
    brackets_index = {
        "‘": "’",
        "“": "”",
        "（": "）",
        "(": ")",
        "［": "］",
        "[": "]",
        "{": "}",
        "｛": "｝",
        "〈": "〉",
        "《": "》",
        "「": "」",
        "『": "』",
        "【": "】",
        "〔": "〕",
        "<": ">",
        "＜": "＞"
    }

    inverted_brackets_table = {v: k for k, v in brackets_index.items()}

    def __init__(self, surfaces):
        self.stack = []
        self.consume_all(surfaces)

    def consume(self, surface):
        if len(self.stack) > 0 and BracketState.inverted_brackets_table.get(surface) == self.stack[-1]:
            self.stack.pop()
        elif surface in BracketState.brackets_index:
            self.stack.append(surface)

    def consume_all(self, surfaces):
        for surface in surfaces:
            self.consume(surface)

    def is_odd(self):
        return not self.is_even()

    def is_even(self):
        return len(self.stack) == 0


class Scanner():
    def __init__(self, nodes, rule, exactly=False):
        self.count = 0
        self.rule = rule
        self.nodes = nodes
        self.exactly = exactly
        self.phrases = [[] for _ in range(len(rule))]

    def consume(self, node):
        if node.pronunciation_length > self.max_consumable_length():
            return False
        elif not node.is_element_of_ikku():
            return False
        elif self.is_first_of_phrase() and not node.is_first_of_phrase():
            return False
        elif node.pronunciation_length == self.max_consumable_length() and not node.is_last_of_phrase():
            return False
        else:
            self.phrases[self.phrase_index()].append(node)
            self.count += node.pronunciation_length
            return True

    def is_first_of_phrase(self):
        return self.count in [sum(self.rule[:i+1]) for i in range(len(self.rule))]

    def is_satisfied(self):
        return self.has_full_count() and self.has_valid_last_node()

    def has_full_count(self):
        return self.count == sum(self.rule)

    def has_valid_first_node(self):
        return self.nodes[0].is_first_of_ikku()

    def has_valid_last_node(self):
        return self.phrases[-1][-1].is_last_of_ikku()

    def max_consumable_length(self):
        return sum(self.rule[:self.phrase_index()+1]) - self.count

    def phrase_index(self):
        for index in range(len(self.rule)):
            if self.count < sum(self.rule[:index+1]):
                return index
        return len(self.rule) - 1

    def scan(self):
        if self.has_valid_first_node():
            for node in self.nodes:
                if self.consume(node):
                    if self.is_satisfied():
                        if not self.exactly:
                            return self.phrases
                else:
                    return
            else:
                if self.is_satisfied():
                    return self.phrases


if __name__ == '__main__':
    # そうなのかなかなか判定難しそう いや別に俳句得意じゃないけどな
    # さっきから下品な川柳いやになる
    # print(haiku_check(input(">>").strip()))

    ikku = Reviewer()
    song = ikku.find("五月雨を\n集めてはやし\n相模川")
    if len(song.surfaces) > 0:
        print(f"{song.surfaces}")
        print("\n".join(["".join([node.surface for node in phrase])
                        for phrase in song.phrases]))
        print(f"{song.season_word}")

        make_ikku_image(
            song, "https://kiritan.work/system/accounts/avatars/000/000/001/original/039525c0ca872f5d.png")
# インストール fribidi  libraqm
