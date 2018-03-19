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
require 'time'
include Clockwork

# --- config
Dotenv.load

# ---
DB_PATH = "db/statuses.db"

# --- debug switch  true false
VERB = false
# VERB = true

############################################################
#
def exe_get_nona(client, max_id = nil)
  if max_id == nil
    return client.public_timeline({:local => true, :limit => 40})
  else
    return client.public_timeline({:local => true, :limit => 40,:max_id => max_id})
  end
end
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
  #今日のトゥートを全取得
  when "hourly"
    pp "スタート"
    break_sw = false
    id =  99999999999999999
    client = Mastodon::REST::Client.new(base_url: ENV["MASTODON_URL"])
    time_b1h = DateTime.now - Rational(1,24)
    statuses_json = {}
    sleep(60*10)
    while true do
      sleep(0.5)
      statuses = exe_get_nona(client, id)
      statuses.each{|status|
        id = status.id.to_i if id > status.id.to_i
        created_at = Time.parse(status.created_at).localtime
        #昨日のトゥートになったら終了
        if time_b1h > created_at
          break_sw = true
          break
        end
        contents = Nokogiri::HTML.parse(status.content)
        text = ''
        contents.search('p').children.each{|item|
          text += item.text.strip  if item.text?
        }
        contents.search('span').children.each{|item|
          text += item.text.strip if item.text?
        }
        statuses_json[status.id] = [created_at, text, status.favourites_count, status.reblogs_count, status.account.acct]
      }
      pp statuses_json.size,statuses_json[id.to_s]
      if break_sw == true
        break
      end
    end
    File.open("db/statuses_hour.json", "w") do |f|
      f.puts(JSON.pretty_generate(statuses_json))
    end

    users_cnt= {}
    users_size= {}
    fav_cnt = {}
    boost_cnt = {}
    faboo_cnt = {}

    statuses_json.each{|id,(created_at,text,f_c,r_c,acct)|
      fav_cnt[id] = f_c
      boost_cnt[id] = r_c
      if users_size.has_key?(acct)
        users_size[acct] += text.size
        users_cnt[acct] += 1
        faboo_cnt[acct] += f_c + r_c
      else
        users_size[acct] = text.size
        users_cnt[acct] = 1
        faboo_cnt[acct] = f_c + r_c
      end
    }

    spoiler_text = "ここ１時間のトゥート数ランキング（勝手にブースター代理）"
    body = ""
    users_cnt.sort_by {|k, v| -v }.each_with_index{|(acct,cnt),i|
      break if i > 9
      body += "🥇 " if i == 0
      body += "🥈 " if i == 1
      body += "🥉 " if i == 2
      body += "🏅 " if i == 3
      body += "🏅 " if i == 4
      body += ":blank: " if i == 5
      body += ":blank: " if i == 6
      body += ":blank: " if i == 7
      body += ":blank: " if i == 8
      body += ":blank: " if i == 9
      body += ":@#{acct}: #{sprintf("%4d",cnt)} toots/ニコブ率 #{sprintf("%3.1f", faboo_cnt[acct].to_f*100/cnt.to_f)}％\n"
      # body += ":@#{acct}: #{sprintf("%4d",cnt)} toots（#{sprintf("%3.1f", users_size[acct].to_f/cnt.to_f)}字/toot） \n"
    }
    body += "#きりランキング #きりぼっと"
    exe_toot(body,visibility = "public",acct = nil,spoiler_text = spoiler_text,rep_id = nil)

    sleep(60)
    spoiler_text = "ここ１時間で最もニコられたトゥートは……"
    body = ""
    fav_cnt.sort_by {|k, v| -v }.each_with_index{|(id,cnt),i|
      break if i > 0
      text = statuses_json[id][1]
      f_c = statuses_json[id][2]
      r_c = statuses_json[id][3]
      acct = statuses_json[id][4]
      body += ":@#{acct}:＜「#{text}」\n#{sprintf("%2d",f_c)}ニコる／#{sprintf("%2d",r_c)}ブースト\n"
      body += "https://friends.nico/web/statuses/#{id}\n"
    }
    body += "#きりランキング #きりぼっと"
    exe_toot(body,visibility = "public",acct = nil,spoiler_text = spoiler_text,rep_id = nil)

  ############################################################
  #今日のトゥートを全取得
  when "daily1"
    pp "スタート"
    break_sw = false
    id =  99999999999999999
    client = Mastodon::REST::Client.new(base_url: ENV["MASTODON_URL"])
    today = Date.today
    statuses_json = {}
    while true do
      sleep(0.2)
      statuses = exe_get_nona(client, id)
      statuses.each{|status|
        id = status.id.to_i if id > status.id.to_i
        created_at = Time.parse(status.created_at).localtime.to_date
        #昨日のトゥートになったら終了
        if today > created_at
          break_sw = true
          break
        end
        if statuses_json.size > 1000
          break_sw = true   if VERB
          break             if VERB
        end
        contents = Nokogiri::HTML.parse(status.content)
        text = ''
        contents.search('p').children.each{|item|
          text += item.text.strip  if item.text?
        }
        contents.search('span').children.each{|item|
          text += item.text.strip if item.text?
        }
        statuses_json[status.id] = [created_at, text, status.favourites_count, status.reblogs_count, status.account.acct]
      }
      pp statuses_json.size,statuses_json[id.to_s]
      if break_sw == true
        break
      end
    end
    File.open("db/statuses_today.json", "w") do |f|
      f.puts(JSON.pretty_generate(statuses_json))
    end

############################################################
# ランキングをトゥート
  when "daily2"
    users_cnt= {}
    users_size= {}
    fav_cnt = {}
    boost_cnt = {}
    faboo_cnt = {}
    statuses_json = {}

    File.open("db/statuses_today.json", "r"){|f|
      statuses_json= JSON.load(f)
    }

    statuses_json.each{|id,(created_at,text,f_c,r_c,acct)|
      fav_cnt[id] = f_c
      boost_cnt[id] = r_c
      if users_size.has_key?(acct)
        users_size[acct] += text.size
        users_cnt[acct] += 1
        faboo_cnt[acct] += f_c + r_c
      else
        users_size[acct] = text.size
        users_cnt[acct] = 1
        faboo_cnt[acct] = f_c + r_c
      end
    }
    faboo_rate = {}
    users_cnt.each{|acct,cnt|
      faboo_rate[acct] = faboo_cnt[acct] * 100 / cnt if cnt >= 10
    }

    File.open("db/users_size.json", "w") do |f|
      f.puts(JSON.pretty_generate(users_size))
    end
    File.open("db/users_cnt.json", "w") do |f|
      f.puts(JSON.pretty_generate(users_cnt))
    end
    File.open("db/faboo_cnt.json", "w") do |f|
      f.puts(JSON.pretty_generate(faboo_cnt))
    end
    File.open("db/faboo_rate.json", "w") do |f|
      f.puts(JSON.pretty_generate(faboo_rate))
    end

    spoiler_text = "今日のトゥート数ランキング（勝手にブースター代理）"
    body = ""
    users_cnt.sort_by {|k, v| -v }.each_with_index{|(acct,cnt),i|
      break if i > 9
      body += "🥇 " if i == 0
      body += "🥈 " if i == 1
      body += "🥉 " if i == 2
      body += "🏅 " if i == 3
      body += "🏅 " if i == 4
      body += ":blank: " if i == 5
      body += ":blank: " if i == 6
      body += ":blank: " if i == 7
      body += ":blank: " if i == 8
      body += ":blank: " if i == 9
      body += ":@#{acct}: #{sprintf("%4d",cnt)} toots/ニコブ率 #{sprintf("%3.1f", faboo_cnt[acct].to_f*100/cnt.to_f)}％\n"
    }
    body += "#きりランキング #きりぼっと"
    exe_toot(body,visibility = "public",acct = nil,spoiler_text = spoiler_text,rep_id = nil)

    sleep(60) unless VERB
    spoiler_text = "今日の影響力（？）ランキング"
    body = ""
    faboo_rate.sort_by {|k, v| -v }.each_with_index{|(acct,cnt),i|
      break if i > 9
      body += "🥇 " if i == 0
      body += "🥈 " if i == 1
      body += "🥉 " if i == 2
      body += "🏅 " if i == 3
      body += "🏅 " if i == 4
      body += ":blank: " if i == 5
      body += ":blank: " if i == 6
      body += ":blank: " if i == 7
      body += ":blank: " if i == 8
      body += ":blank: " if i == 9
      body += ":@#{acct}:ニコブ率 #{sprintf("%4d",cnt)}％\n"
    }
    body += "※10トゥート未満の人は除外\n#きりランキング #きりぼっと"
    exe_toot(body,visibility = "public",acct = nil,spoiler_text = spoiler_text,rep_id = nil)

    sleep(60) unless VERB
    spoiler_text = "今日最もニコられたトゥートは……"
    body = ""
    fav_cnt.sort_by {|k, v| -v }.each_with_index{|(id,cnt),i|
      break if i > 0
      text = statuses_json[id][1]
      f_c = statuses_json[id][2]
      r_c = statuses_json[id][3]
      acct = statuses_json[id][4]
      body += ":@#{acct}:＜「#{text}」\n#{sprintf("%2d",f_c)}ニコる／#{sprintf("%2d",r_c)}ブースト\n"
      body += "https://friends.nico/web/statuses/#{id}\n"
    }
    body += "#きりランキング #きりぼっと"
    exe_toot(body,visibility = "public",acct = nil,spoiler_text = spoiler_text,rep_id = nil)
  end
end

every(1.day, 'daily1', at: '23:12')      unless VERB
every(1.day, 'daily2', at: '23:30')      unless VERB
every(1.hour, 'hourly', at: '**:00')      unless VERB
every(1.week, 'daily2')   if VERB
# every(1.week, 'hourly')
