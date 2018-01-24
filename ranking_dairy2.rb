# coding: utf-8
require 'mastodon'
require 'nokogiri'
require 'json'
require 'dotenv'
require 'pp'
#require 'clockwork'
require 'fileutils'
require 'sqlite3'
require 'date'
include Clockwork


# --- config
Dotenv.load

# ---
DB_PATH = "db/statuses.db"
DB_PATH_TMP = "db/statuses_tmp.db"
#USER_PATH = "Daily_#{Time.now.strftime('%Y%m%d')}/"


# --- debug switch  true false
VERB = false

############################################################
#トゥートメソッド
def exe_toot(body,visibility = "public",acct = nil,spoiler_text = nil,rep_id = nil)
  #おまじないー！
  client = Mastodon::REST::Client.new(base_url: ENV["MASTODON_URL"],
                                      bearer_token: ENV["MASTODON_ACCESS_TOKEN"])
  acct = "@"+acct if acct != nil
  #トゥート！
  puts "#{body},#{acct},#{visibility},#{spoiler_text},#{rep_id}"    if VERB
  client.create_status_kiri( "#{body[0,460]}#{acct}" , visibility ,spoiler_text,rep_id)  unless VERB
end

############################################################
#メイン処理
handler do |job|
  case job
  ############################################################
  #累計トゥート文字数カウント
  when "main1"
    FileUtils.cp(DB_PATH, DB_PATH_TMP)
    sleep(30)
    db = SQLite3::Database.new(DB_PATH_TMP,{:timeout => 120000})
    #累計トゥーと文字数カウント
    sql = "select acct,content from statuses;"
    users_cnt = {}
    db.execute(sql).each {|acct,content|

      contents = Nokogiri::HTML.parse(content)
      text = ''
      contents.search('p').children.each{|item|
        text += item.text.strip  if item.text?
      }
      contents.search('span').children.each{|item|
        text += item.text.strip if item.text?
      }

      if users_cnt.has_key?(acct)
        users_cnt[acct] += text.size
      else
        users_cnt[acct] = text.size
      end
    }
    users_cnt = users_cnt.sort {|(k1, v1), (k2, v2)| v2 <=> v1 }
    File.open("work/users_cnt.txt", "w") do |f|
      f.puts(JSON.pretty_generate(users_cnt))
    end
    db.close

  ############################################################
  #当日トゥート文字数カウント
  when "main2"
    db = SQLite3::Database.new(DB_PATH_TMP,{:timeout => 120000})
    today = Time.now.strftime('%Y%m%d')

    #今日のトゥート文字数カウント
    sql = "select acct,content from statuses where date=#{today};"
    users_cnt_today = {}
    db.execute(sql).each {|acct,content|

      contents = Nokogiri::HTML.parse(content)
      text = ''
      contents.search('p').children.each{|item|
        text += item.text.strip  if item.text?
      }
      contents.search('span').children.each{|item|
        text += item.text.strip if item.text?
      }

      if users_cnt_today.has_key?(acct)
        users_cnt_today[acct] += text.size
      else
        users_cnt_today[acct] = text.size
      end
    }
    users_cnt_today = users_cnt_today.sort {|(k1, v1), (k2, v2)| v2 <=> v1 }
    File.open("work/users_cnt_today.txt", "w") do |f|
      f.puts(JSON.pretty_generate(users_cnt_today))
    end
    db.close

  ############################################################
  #ランキング作成してトゥート
  when "main3"
    users_cnt= {}
    File.open("work/users_cnt.txt", "r"){|f|
      users_cnt= JSON.load(f)
    }
    users_cnt_today= {}
    File.open("work/users_cnt_today.txt", "r"){|f|
      users_cnt_today= JSON.load(f)
    }

    ruikei_rank = {}
    users_cnt.each_with_index{|(acct,cnt),i|
      ruikei_rank[acct] = [i,cnt]
    }

    char_cnt = 0
    users_cnt_today.each_with_index{|(acct,cnt),i|
      char_cnt += cnt
      pp "#{i+1}位 :@#{acct}: #{cnt}字(累計#{ruikei_rank[acct][0]+1}位：#{ruikei_rank[acct][1]}字)"
    }
    body = "📝#{char_cnt}字/💁#{users_cnt_today.size}人\nトゥートした「文字数」のランキングだよー！"

    users_cnt_today.each_with_index{|(acct,cnt),i|
      break if i > 9
      body += "#{sprintf("%2d",i+1)}位 :@#{acct}: #{sprintf("%5d",cnt)}字(累計#{ruikei_rank[acct][0]+1}位：#{sprintf("%3d",ruikei_rank[acct][1]/10000)}万字)\n"
    }
    exe_toot(body,visibility = "unlisted",acct = nil,spoiler_text = "きりたん勝手にランキング",rep_id = nil)

  end
end

every(1.day, 'main1', at: '22:00')      unless VERB
every(1.day, 'main2', at: '22:40')      unless VERB
every(1.day, 'main3', at: '22:50')      unless VERB
every(1.week, 'main3')   if VERB
#every(1.week, 'main3')
