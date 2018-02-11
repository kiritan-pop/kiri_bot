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

#USER_PATH = "Daily_#{Time.now.strftime('%Y%m%d')}/"

# --- debug switch  true false
VERB = true

############################################################
#トゥートメソッド
def exe_toot(body,visibility = "public",acct = nil,spoiler_text = nil,rep_id = nil)
  #おまじないー！
  client = Mastodon::REST::Client.new(base_url: ENV["MASTODON_URL"],
                                      bearer_token: ENV["MASTODON_ACCESS_TOKEN"])
  acct = "@"+acct if acct != nil
  #トゥート！
  puts "#{body}" #{}",#{acct},#{visibility},#{spoiler_text},#{rep_id}"    if VERB
  client.create_status_kiri( "#{body[0,460]}#{acct}" , visibility ,spoiler_text,rep_id)  unless VERB
end

############################################################
#メイン処理
handler do |job|
  case job
  ############################################################
  #１ＷＥＥＫのトゥートからステータスを更新
  when "main"
    pp "スタート"
    db = SQLite3::Database.new(DB_PATH,{:timeout => 120000})
    today = Time.now.strftime('%Y%m%d')
    day_b1w = (Time.now - 3*24*60*60).strftime('%Y%m%d')

    #今日のトゥート文字数カウント
    sql = "select acct, content, media_attachments from statuses where date <=#{today} and date >=#{day_b1w};"
    users_statuses = {}
    tmp_users_chars_cnt = {}
    tmp_users_chars_size = {}
    tmp_attack = {}
    tmp_magic = {}
    db.execute(sql).each {|acct,content,media_attachments|

      contents = Nokogiri::HTML.parse(content)
      text = ''
      contents.search('p').children.each{|item|
        text += item.text.strip  if item.text?
      }
      contents.search('span').children.each{|item|
        text += item.text.strip if item.text?
      }

      if tmp_users_chars_size.has_key?(acct)
        tmp_users_chars_size[acct] += text.size
        tmp_users_chars_cnt[acct] += 1
      else
        tmp_users_chars_size[acct] = text.size
        tmp_users_chars_cnt[acct] = 1
      end

      if tmp_magic.has_key?(acct)
        tmp_magic[acct] += media_attachments.split(" ").size
      else
        tmp_magic[acct] = media_attachments.split(" ").size
      end

    }

    #攻撃力
    File.open("kiri_game/tmp_users_chars_size.json", "w") do |f|
      f.puts(JSON.pretty_generate(tmp_users_chars_size))
    end
    File.open("kiri_game/tmp_users_chars_cnt.json", "w") do |f|
      f.puts(JSON.pretty_generate(tmp_users_chars_cnt))
    end
    tmp_users_chars_size.each do |acct,size|
        tmp_attack[acct] = (size.to_f*10/tmp_users_chars_cnt[acct].to_f ).to_i
    end
    File.open("kiri_game/tmp_attack.json", "w") do |f|
      f.puts(JSON.pretty_generate(tmp_attack))
    end
    File.open("kiri_game/tmp_magic.json", "w") do |f|
      f.puts(JSON.pretty_generate(tmp_magic))
    end

    db.close

    pp "エンド"

  ############################################################
  #ランキング作成してトゥート
  when "main3"
    #累計分
    users_cnt= {}
    users_size= {}
    File.open("db/users_cnt.json", "r"){|f|
      users_cnt= JSON.load(f)
    }
    File.open("db/users_size.json", "r"){|f|
      users_size= JSON.load(f)
    }

    #本日分
    users_cnt_today= {}
    users_size_today= {}
    File.open("db/users_cnt_today.json", "r"){|f|
      users_cnt_today= JSON.load(f)
    }
    File.open("db/users_size_today.json", "r"){|f|
      users_size_today= JSON.load(f)
    }

    ruikei_rank = {}
    users_size.sort_by {|k, v| -v }.each_with_index{|(acct,size),i|
      ruikei_rank[acct] = [i,size]
    }

    char_size = 0
    char_cnt = 0
    users_size_today.sort_by {|k, v| -v }.each_with_index{|(acct,size),i|
      char_size += size
      char_cnt += users_cnt_today[acct]
      #pp "#{i+1}位 :@#{acct}: #{size}字(累計#{ruikei_rank[acct][0]+1}位：#{ruikei_rank[acct][1]}字)"
    }

    body = "📝#{char_size}字:#{char_cnt}toot:💁#{users_size_today.size}人\nトゥートした「文字数」のランキングだよー！\n"
    users_size_today.sort_by {|k, v| -v }.each_with_index{|(acct,size),i|
      break if i > 6 &&  VERB == false
      body += "#{sprintf("%2d",i+1)}位 :@#{acct}: #{sprintf("%5d",size)}字（#{sprintf("%3.1f", size.to_f/users_cnt_today[acct].to_f)}字/toot） \n"
      body += "　　　　（累計#{ruikei_rank[acct][0]+1}位：#{sprintf("%3d",ruikei_rank[acct][1]/10000)}万字）\n"
    }
    body += "#きりランキング #きりぼっと"
    exe_toot(body,visibility = "public",acct = nil,spoiler_text = "きりたん勝手にランキング",rep_id = nil)

    users_cnt= {}
    users_size= {}
    users_cnt_today = {}
    users_size_today = {}


  end
end

every(1.week, 'main', at: '22:00')      unless VERB
every(1.week, 'main')   if VERB
