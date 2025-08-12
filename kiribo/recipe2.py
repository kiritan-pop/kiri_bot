from typing import List
from kiribo.openai_service import predict, is_alive
import json
import os
from PIL import Image, ImageFont, ImageDraw
from kiribo.config import settings
from kiribo.util import logger
import re


SYSTEM_PROMPT = """あなたは与えられたメイン食材を元に独創的な料理を考え、そのレシピを提案してください。
メイン食材の他に必要な調味料や食材もあわせて記載してください。
可能な限り日本語で出力してください。

出力フォーマット
```json
{
"材料・調味料" : {
    "材料名1": "分量",
    "材料名2": "分量"
    },
"料理手順": {
    "1.手順タイトル": "料理手順",
    "2.手順タイトル": "料理手順"
    },
"料理名" : "独創的な料理名（詩的表現を使って）"
}
```

** "分量"の記載例 **
  150g, 200ml, 小さじ2, 大さじ1, 1個, 2枚, 3本, ひとつまみ, 少々, お好みで


出力例１
input:
卵, 牛肉, タマネギ, もやし

output:
```json
{
  "材料・調味料": {
    "卵": "3個",
    "牛肉": "200g",
    "タマネギ": "1個",
    "もやし": "100g",
    "醤油": "大さじ2",
    "みりん": "大さじ1",
    "砂糖": "小さじ1",
    "塩": "少々",
    "コショウ": "少々",
    "ごま油": "小さじ1",
    "万能ねぎ": "お好みで"
  },
  "料理手順": {
    "1.下ごしらえ": "牛肉は一口大に切り、醤油、みりん、砂糖で5分ほど下味をつけます。タマネギは薄切り、もやしは軽く洗って水気を切ります。",
    "2.牛肉とタマネギを炒める": "フライパンにごま油を熱し、牛肉を炒めます。色が変わったらタマネギを加えて炒め、しんなりしたら取り出します。",
    "3.卵の準備": "ボウルに卵を割り入れ、塩とコショウを少々加えて軽く混ぜます。",
    "4.卵ともやしの調理": "同じフライパンにもやしを軽く炒め、塩少々で味を調えます。その上に溶き卵を流し入れ、ふんわりと固まるまで弱火で火を通します。",
    "5.仕上げ": "卵ともやしの上に炒めた牛肉とタマネギを乗せ、万能ねぎを散らして完成です。"
  },
  "料理名": "彩り舞う卵の花畑 ～牛肉とタマネギの調べ～"
}
```

--
メイン食材は以下の通りです。
input:
"""


def create_recipe_image(recipe_data):
    """レシピデータから画像を生成する"""
    try:
        # レシピデータをパース
        if isinstance(recipe_data, str):
            # JSON部分を抽出
            json_start = recipe_data.find('```json')
            json_end = recipe_data.find('```', json_start + 7)
            if json_start != -1 and json_end != -1:
                json_str = recipe_data[json_start + 7:json_end].strip()
                recipe = json.loads(json_str)
            else:
                logger.error("JSONデータが見つかりません")
                return None
        else:
            recipe = recipe_data

        # 画像サイズの設定
        IMAGE_WIDTH = 900
        IMAGE_HEIGHT = 1400
        MARGIN = 50
        LINE_HEIGHT = 35
        SECTION_MARGIN = 30
        TABLE_MARGIN = 20

        # 画像作成
        image = Image.new("RGBA", (IMAGE_WIDTH, IMAGE_HEIGHT),
                          (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)

        # フォント設定
        title_font = ImageFont.truetype(settings.font_path, 32)
        section_font = ImageFont.truetype(settings.font_path, 24)
        content_font = ImageFont.truetype(settings.font_path, 20)
        small_font = ImageFont.truetype(settings.font_path, 18)
        table_font = ImageFont.truetype(settings.font_path, 18)

        # 色設定
        title_color = (50, 50, 50)
        section_color = (80, 80, 80)
        content_color = (60, 60, 60)
        accent_color = (220, 100, 100)
        table_header_color = (240, 240, 240)
        table_border_color = (200, 200, 200)

        current_y = MARGIN

        # タイトル（料理名）
        title = recipe.get("料理名", "レシピ")
        # タイトルが長い場合は改行処理
        if len(title) > 25:
            title_lines = []
            for i in range(0, len(title), 25):
                title_lines.append(title[i:i+25])
            for line in title_lines:
                draw.text((MARGIN, current_y), line,
                          font=title_font, fill=accent_color)
                current_y += title_font.size + 5
        else:
            draw.text((MARGIN, current_y), title,
                      font=title_font, fill=accent_color)
            current_y += title_font.size + 5

        current_y += SECTION_MARGIN

        # 材料・調味料セクション（テーブル形式）
        draw.text((MARGIN, current_y), "【材料・調味料】",
                  font=section_font, fill=section_color)
        current_y += section_font.size + 15

        ingredients = recipe.get("材料・調味料", {})
        if ingredients:
            # テーブルヘッダー
            header_bg_rect = [MARGIN, current_y,
                              IMAGE_WIDTH - MARGIN, current_y + 40]
            draw.rectangle(header_bg_rect, fill=table_header_color)
            draw.text((MARGIN + 10, current_y + 10), "材料名",
                      font=table_font, fill=section_color)
            draw.text((MARGIN + 400, current_y + 10), "分量",
                      font=table_font, fill=section_color)
            current_y += 40

            # テーブルボーダー（ヘッダー下の横線）
            draw.line([MARGIN, current_y, IMAGE_WIDTH - MARGIN,
                      current_y], fill=table_border_color, width=2)

            # 縦線（材料名と分量の境界）
            draw.line([MARGIN + 350, current_y - 40, MARGIN + 350,
                      current_y], fill=table_border_color, width=2)

            # 材料リスト
            for ingredient, amount in ingredients.items():
                # 材料名
                if len(ingredient) > 15:
                    ingredient_lines = []
                    for i in range(0, len(ingredient), 15):
                        ingredient_lines.append(ingredient[i:i+15])
                    for line in ingredient_lines:
                        draw.text((MARGIN + 10, current_y + 5), line,
                                  font=content_font, fill=content_color)
                        current_y += LINE_HEIGHT - 5
                    current_y += 5
                else:
                    draw.text((MARGIN + 10, current_y + 5), ingredient,
                              font=content_font, fill=content_color)
                    current_y += LINE_HEIGHT

                # 分量
                draw.text((MARGIN + 400, current_y - LINE_HEIGHT + 5),
                          amount, font=content_font, fill=content_color)

                # 行の境界線（横線）
                draw.line([MARGIN, current_y, IMAGE_WIDTH - MARGIN,
                          current_y], fill=table_border_color, width=1)

            # 最後の縦線を延長（材料リストの最後まで）
            draw.line([MARGIN + 350, current_y - len(ingredients) * LINE_HEIGHT,
                      MARGIN + 350, current_y], fill=table_border_color, width=2)

        current_y += SECTION_MARGIN

        # 料理手順セクション
        draw.text((MARGIN, current_y), "【料理手順】",
                  font=section_font, fill=section_color)
        current_y += section_font.size + 15

        steps = recipe.get("料理手順", {})
        step_number = 1
        for step_title, step_content in steps.items():
            # 手順番号とタイトル（既存の番号を除去してから番号を追加）
            # 既存の番号パターンを除去（1.手順タイトル、2.手順タイトルなど）
            clean_title = step_title
            # 数字.で始まる場合、その部分を除去
            if re.match(r'^\d+\.', clean_title):
                clean_title = re.sub(r'^\d+\.\s*', '', clean_title)

            step_header = f"{step_number}. {clean_title}"
            draw.text((MARGIN, current_y), step_header,
                      font=content_font, fill=accent_color)
            current_y += LINE_HEIGHT

            # 手順内容（長い場合は改行処理）
            if len(step_content) > 45:
                # より自然な改行処理
                words = step_content.split('。')
                for word in words:
                    if word.strip():
                        if len(word) > 45:
                            # 長い文章は45文字ごとに改行
                            for i in range(0, len(word), 45):
                                line = word[i:i+45]
                                draw.text((MARGIN + 20, current_y), line,
                                          font=small_font, fill=content_color)
                                current_y += LINE_HEIGHT - 5
                        else:
                            draw.text((MARGIN + 20, current_y), word +
                                      "。", font=small_font, fill=content_color)
                            current_y += LINE_HEIGHT - 5
            else:
                draw.text((MARGIN + 20, current_y), step_content,
                          font=small_font, fill=content_color)
                current_y += LINE_HEIGHT - 5

            current_y += 10
            step_number += 1

        # フッター情報
        footer_y = IMAGE_HEIGHT - 60
        draw.text((MARGIN, footer_y), "※ 分量は目安です。お好みで調整してください。",
                  font=small_font, fill=(150, 150, 150))

        # 画像を保存
        file_path = os.path.join(settings.media_path, "tmp_recipe.png")
        image.save(file_path, "PNG")
        logger.info(f"レシピ画像を生成しました: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"レシピ画像生成中にエラーが発生しました: {e}")
        return None


def create_recipe_post_text(recipe_data):
    """レシピ投稿用の短いテキストを生成する"""
    try:
        if isinstance(recipe_data, str):
            # JSON部分を抽出
            json_start = recipe_data.find('```json')
            json_end = recipe_data.find('```', json_start + 7)
            if json_start != -1 and json_end != -1:
                json_str = recipe_data[json_start + 7:json_end].strip()
                recipe = json.loads(json_str)
            else:
                return "レシピの生成に失敗しました"
        else:
            recipe = recipe_data

        # 料理名
        recipe_name = recipe.get("料理名", "レシピ")

        # 材料の数
        ingredients_count = len(recipe.get("材料・調味料", {}))

        # 手順の数
        steps_count = len(recipe.get("料理手順", {}))

        # 短い投稿文を生成（500文字以内）
        post_text = f"🍳 {recipe_name}\n\n"
        post_text += f"📝 材料: {ingredients_count}種類\n"
        post_text += f"👨‍🍳 手順: {steps_count}ステップ\n\n"
        post_text += "詳細なレシピは画像をご確認ください！\n"
        post_text += "#料理 #レシピ #自炊"

        return post_text

    except Exception as e:
        logger.error(f"レシピ投稿文生成中にエラーが発生しました: {e}")
        return "レシピの生成に失敗しました"


def get_recipe_with_image(zairyo_list: List):
    """食材リストからレシピを取得し、投稿用テキストと画像ファイルパスを返す"""
    if is_alive():
        user_prompt = ",".join(zairyo_list)
        response = predict(SYSTEM_PROMPT, user_prompt)

        if response:
            # レシピ画像を生成
            image_path = create_recipe_image(response)

            # 投稿用テキストを生成
            post_text = create_recipe_post_text(response)

            return {
                "full_text": response,
                "post_text": post_text,
                "image_path": image_path
            }
        else:
            return None
    else:
        return None


def get_recipe(zairyo_list: List):
    """食材リストからレシピを取得し、画像ファイルパスを返す（後方互換性のため）"""
    if is_alive():
        user_prompt = ",".join(zairyo_list)
        response = predict(SYSTEM_PROMPT, user_prompt)

        if response:
            # レシピ画像を生成
            image_path = create_recipe_image(response)
            return {
                "text": response,
                "image_path": image_path
            }
        else:
            return None
    else:
        return None
