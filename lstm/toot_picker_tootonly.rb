# coding: utf-8
require 'nokogiri'
require 'json'
require 'dotenv'
require 'pp'
require 'sqlite3'


# --- config
Dotenv.load

# --- debug switch  true false
VERB = false

############################################################
#メイン処理
marge_text = ""
mediatext1b = ""
username = ''
i = 0
db = SQLite3::Database.new('../db/statuses.db',:timeout=>1200)
f_toot = File.open('toot.txt', "w")

sql = "select id,content from statuses where acct <> 'kiri_bot01' and acct <> 'hiho_karuta' and acct <> 'nia_null' order by id desc"
db.execute(sql)  { |id,content|
  contents = Nokogiri::HTML.parse(content)
  text = ''
  contents.search('p').children.each{|item|
    text += item.text.strip  if item.text?
  }
  f_toot.puts('📣'+text)
  break if i > 1000000
  i += 1
}

db.close
f_toot.close
