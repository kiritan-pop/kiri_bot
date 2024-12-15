# coding: utf-8
from pydantic_settings import BaseSettings, SettingsConfigDict
from pytz import timezone


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='allow')

    # botが接続するマストドンサーバ、接続情報（必須）
    mastodon_url: str = 'https://example.com'
    mastodon_access_token: str = '****'

    # 特殊ユーザid
    master_id: str = 'example'
    bot_id: str = 'example_bot'

    # ua
    ua: str = 'development'
    # google検索api用key
    google_key: str = "****"
    google_engine_key: str = "****"

    log_level: str = 'INFO'  # DEBUG,INFO,WARN,ERROR,CRITICAL

    # 各種データ置き場
    media_path: str
    bot_list_path: str
    kaomoji_path : str
    kora_path: str
    nade_path: str
    hinpined_words_path: str
    watch_list_path: str
    no_bottle_path: str
    recipe_z_path: str
    recipe_a_path: str
    statuses_db_path: str
    db_schema_path: str
    emoji_path: str
    siritori_dic_path: str
    city_latloc_path: str
    twotwo_dic_path: str
    ng_words_path: str
    bottlemail_db_path: str
    bottlemail_schema_path: str
    log_path: str
    kigo_path: str
    tarot_data_path: str
    tarot_img_path: str
    tarot_chk_path: str
    tarot_imgmap_path: str
    tarot_april_data_path: str
    tarot_april_img_path: str
    font_path: str
    font_path_ikku: str
    weather_images: str
    weather_area: str

    timezone_str: str = "Asia/Tokyo"

    @property
    def timezone(self):
        return timezone(self.timezone_str)
    
    openai_api_base: str
    openai_api_key: str
    openai_model: str
    openai_temperature: float


settings = Settings()