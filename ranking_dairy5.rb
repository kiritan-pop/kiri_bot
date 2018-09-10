#!/usr/bin/env ruby
# coding: utf-8
require 'mastodon'
require 'net/http'
require 'nokogiri'
require 'json'
require 'dotenv'
require 'pp'
require 'clockwork'
require 'fileutils'
require 'sqlite3'
require 'date'
require 'time'
include Clockwork
require 'active_support/time'

# --- config
Dotenv.load

# ---
DB_PATH = "db/statuses.db"

# --- debug switch  true false
VERB = false
# VERB = true

asikiri_h = 5
asikiri_d = 20

############################################################
#
def exe_get_nona(max_id = nil)
  client = Mastodon::REST::Client.new(base_url: ENV["MASTODON_URL"])
  if max_id == nil
    return client.public_timeline({:local => true, :limit => 40})
  else
    return client.public_timeline({:local => true, :limit => 40,:max_id => max_id})
  end
end
############################################################
#トゥートメソッド
def exe_toot(body,visibility = "public",acct = nil,spoiler_text = nil,rep_id = nil,media_ids = [])
  #おまじないー！
  client = Mastodon::REST::Client.new(base_url: ENV["MASTODON_URL"],
                                      bearer_token: ENV["MASTODON_ACCESS_TOKEN"])
  acct = "@"+acct if acct != nil
  #トゥート！
  puts "exe_toot(#{body},#{acct},#{visibility},#{spoiler_text},#{rep_id},#{media_ids})"    if VERB
  begin
    # client.create_status_kiri( "#{body[0,460]}#{acct}" , 'private' ,spoiler_text,rep_id, media_ids = media_ids)  unless VERB
    client.create_status_kiri( "#{body[0,460]}#{acct}" , visibility ,spoiler_text,rep_id, media_ids = media_ids)  unless VERB
  rescue => e
    pp "exe_toot error!",e
  end
end
############################################################
#トゥートメソッド
def exe_boost(id)
  #おまじないー！
  client = Mastodon::REST::Client.new(base_url: ENV["MASTODON_URL"],
                                      bearer_token: ENV["MASTODON_ACCESS_TOKEN"])
  puts "exe_boost(#{id})" if VERB
  begin
    client.reblog(id) unless VERB
  rescue => e
    pp "exe_boost error!",e
  end
end
############################################################
#メディアアップロード
def exe_upload_media(path)
  #おまじないー！
  client = Mastodon::REST::Client.new(base_url: ENV["MASTODON_URL"],
                                      bearer_token: ENV["MASTODON_ACCESS_TOKEN"])
  begin
    return client.upload_media(data)
  rescue => e
    pp "exe_upload_media error!",e
  end
end

############################################################
#メイン処理
handler do |job|
  case job
  ############################################################
  #1時間のトゥートを全取得
  when "hourly1"
    pp "スタート"
    break_sw = false
    # id =  999999999999999999
    id =  nil
    time_now = DateTime.now
    time_b1h = time_now - Rational(1,24)
    statuses_json = {}
    sleep(60*10)  unless VERB
    while true do
      sleep(0.2)
      statuses = exe_get_nona(id)
      statuses.each{|status|
        id = status.id.to_i if id == nil or id > status.id.to_i
        media_urls = []
        status.media_attachments.each{|media|
          media_urls.push(media.url)
        }
        created_at = Time.parse(status.created_at).localtime
        #昨日のトゥートになったら終了
        if time_b1h > created_at
          break_sw = true
          break
        end
        if created_at <= time_now
          contents = Nokogiri::HTML.parse(status.content)
          text = ''
          contents.search('p').children.each{|item|
            text += " " + item.text.strip  + " "   if item.text?
          }
          contents.search('span').children.each{|item|
            text += item.text.strip if item.text?
            # text += item.text.strip if item.text?
          }
          statuses_json[status.id] = [created_at, text, status.favourites_count, status.reblogs_count, status.account.acct, media_urls]
        end
      }
      pp statuses_json.size,statuses_json[id.to_s]
      if break_sw == true
        break
      end
    end
    File.open("db/statuses_hour.json", "w") do |f|
      f.puts(JSON.pretty_generate(statuses_json))
    end

  ############################################################
  when "hourly2"
    users_cnt= {}
    users_size= {}
    fav_cnt = {}
    boost_cnt = {}
    faboo_cnt = {}
    fav_acct_cnt = {}
    faboo_rate = {}
    faboo_cnt_list = {}

    File.open("db/statuses_hour.json", "r"){|f|
      statuses_json= JSON.load(f)
    }

    statuses_json.each{|id,(created_at,text,f_c,r_c,acct,media_urls)|
      fav_cnt[id] = f_c
      boost_cnt[id] = r_c

      if users_size.has_key?(acct)
        users_size[acct] += text.size
        users_cnt[acct] += 1
        fav_acct_cnt[acct] += f_c
        faboo_cnt[acct] += f_c + r_c
        faboo_cnt_list[acct].push(f_c + r_c)
      else
        users_size[acct] = text.size
        users_cnt[acct] = 1
        fav_acct_cnt[acct] = f_c
        faboo_cnt[acct] = f_c + r_c
        faboo_cnt_list[acct] = []
        faboo_cnt_list[acct].push(f_c + r_c)
      end
      faboo_rate[acct] = faboo_cnt[acct].to_f * 100.0 / users_cnt[acct].to_f if users_cnt[acct] >= asikiri_h
    }

    spoiler_text = "毎時トゥート数ランキング"
    body = ""
    total_cnt = 0
    total_faboo_cnt = 0
    users_cnt.sort_by {|k, v| -v }.each_with_index{|(acct,cnt),i|
      total_cnt += cnt
      total_faboo_cnt += faboo_cnt[acct]
      if body.length < 420
        body += "🥇 " if i == 0
        body += "🥈 " if i == 1
        body += "🥉 " if i == 2
        body += "🏅 " if i == 3
        body += "🏅 " if i == 4
        # body += ":blank: " if i >= 5
        body += ":@#{acct}:#{sprintf("%3d",cnt)}  "
        body += "\n" if i.modulo(3) == 1 or i <= 4
      end
    }
    body = "📝全体 #{total_cnt} toots\n" + body
    body += "\n#きりランキング #きりぼっと"
    exe_toot(body,visibility = "public",acct = nil,spoiler_text = spoiler_text,rep_id = nil)

    #ニコられランキング
    sleep(60) unless VERB
    spoiler_text = "毎時ニコられ数ランキング"
    body = ""
    total_fav_cnt = 0
    fav_acct_cnt.sort_by {|k, v| -v }.each_with_index{|(acct,cnt),i|
      total_fav_cnt += cnt
      if body.length < 420
        body += "🥇 " if i == 0
        body += "🥈 " if i == 1
        body += "🥉 " if i == 2
        body += "🏅 " if i == 3
        body += "🏅 " if i == 4
        # body += ":blank: " if i >= 5
        body += ":@#{acct}:#{sprintf("%3d",cnt)}  "
        body += "\n" if i.modulo(3) == 1 or i <= 4
      end
    }
    body = "📝全体 #{total_fav_cnt} ニコる\n" + body
    body += "\n#きりランキング #きりぼっと"
    exe_toot(body,visibility = "public",acct = nil,spoiler_text = spoiler_text,rep_id = nil)

    sleep(60) unless VERB
    spoiler_text = "毎時ニコブ率ランキング"
    body = ""
    faboo_rate.sort_by {|k, v| -v }.each_with_index{|(acct,rate),i|
      # break if i > 10
      break if body.length > 380
      body += "🥇 " if i == 0
      body += "🥈 " if i == 1
      body += "🥉 " if i == 2
      body += "🏅 " if i == 3
      body += "🏅 " if i == 4
      # body += ":blank: " if i >= 5
      # body += ":@#{acct}:#{sprintf("%6.1f",rate)} ％ #{sprintf("%4d",faboo_cnt[acct])}/#{sprintf("%4d",users_cnt[acct])}\n"
      body += ":@#{acct}:#{sprintf("%6.1f",rate)}％  "
      body += "\n" if i.modulo(2) == 0 or i <= 4
    }
    body += "\n※ニコブ率：（ニコられ数＋ブーストされ数）÷トゥート数\n"
    body += "※#{asikiri_h}トゥート未満の人は除外\n#きりランキング #きりぼっと"
    exe_toot(body,visibility = "public",acct = nil,spoiler_text = spoiler_text,rep_id = nil)

    # faboo_peak_rate_list = {}
    # faboo_cnt_list.each{|acct,list|
    #   tmp = list.sort{|a,b| b <=> a }
    #   if tmp.length >= asikiri_h
    #     sum = 0
    #     for v in tmp[0..asikiri_h] do
    #       sum += v
    #     end
    #     faboo_peak_rate_list[acct] = sum.to_f/asikiri_h.to_f * 100.0
    #   end
    # }

    # spoiler_text = "毎時ピークニコブ率ランキング"
    # body = ""
    # faboo_peak_rate_list.sort_by {|k, v| -v }.each_with_index{|(acct,rate),i|
    #   break if body.length > 380
    #   body += "🥇 " if i == 0
    #   body += "🥈 " if i == 1
    #   body += "🥉 " if i == 2
    #   body += "🏅 " if i == 3
    #   body += "🏅 " if i == 4
    #   body += ":@#{acct}:#{sprintf("%4.0f",rate)}％  "
    #   body += "\n" if i.modulo(2) == 0 or i <= 4
    # }
    # body += "\n※ニコブ率：（ニコられ数＋ブーストされ数）÷トゥート数"
    # body += "\n※ピークニコブ率：各位の高ニコブな#{asikiri_h}トゥートのニコブ率"
    # body += "\n#きりランキング #きりぼっと"
    # exe_toot(body,visibility = "public",acct = nil,spoiler_text = spoiler_text,rep_id = nil)

    sleep(60) unless VERB
    fav_cnt.sort_by {|k, v| -v }.each_with_index{|(id,cnt),i|
      break if i > 0
      exe_boost(id)
      sleep(5)
      text = statuses_json[id][1]
      f_c = statuses_json[id][2]
      r_c = statuses_json[id][3]
      acct = statuses_json[id][4]
      urls = statuses_json[id][5]
      media_ids = []
      # urls.each{|url|
        # media_path = "./media/" + url.split("/").last
        # media = exe_upload_media(media_path)
        # p "url=#{url}"
        # p "media_path=#{media_path}"
        # p "media=#{media}"
        # media_ids.push(media.id) if media != nil
      # }

      body = ":@#{acct}:＜「#{text} 」\n#{sprintf("%2d",f_c)}ニコる／#{sprintf("%2d",r_c)}ブースト"
      body += "\n https://friends.nico/@#{acct}/#{id}"
      body += "\n#きりランキング #きりぼっと"
      exe_toot(body,visibility = "public",acct = nil,spoiler_text = "ここ１時間で最もニコられたトゥートは……",rep_id = nil,media_ids=media_ids)
    }

  ############################################################
  #今日のトゥートを全取得
  when "daily1"
    pp "スタート"
    break_sw = false
    id =  nil
    today = Date.today
    # today = today - Rational(1,1)

    statuses_json = {}
    while true do
      sleep(0.2)
      statuses = exe_get_nona(id)
      statuses.each{|status|
        id = status.id.to_i if id == nil or id > status.id.to_i
        # id = status.id.to_i if id > status.id.to_i
        media_ids = []
        status.media_attachments.each{|media|
          media_ids.push(media.id)
        }
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
          text += " " + item.text.strip  + " "   if item.text?
        }
        contents.search('span').children.each{|item|
          text += item.text.strip if item.text?
        }
        statuses_json[status.id] = [created_at, text, status.favourites_count, status.reblogs_count, status.account.acct, media_ids]
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
    fav_acct_cnt = {}
    statuses_json = {}
    faboo_rate = {}

    File.open("db/statuses_today.json", "r"){|f|
      statuses_json= JSON.load(f)
    }

    statuses_json.each{|id,(created_at,text,f_c,r_c,acct,media_ids)|
      fav_cnt[id] = f_c
      boost_cnt[id] = r_c
      if users_size.has_key?(acct)
        users_size[acct] += text.size
        users_cnt[acct] += 1
        faboo_cnt[acct] += f_c + r_c
        fav_acct_cnt[acct] += f_c
      else
        users_size[acct] = text.size
        users_cnt[acct] = 1
        faboo_cnt[acct] = f_c + r_c
        fav_acct_cnt[acct] = f_c
      end
      faboo_rate[acct] = faboo_cnt[acct].to_f * 100.0 / users_cnt[acct].to_f if users_cnt[acct] >= asikiri_d
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

    spoiler_text = "今日のトゥート数ランキング"
    body = ""
    total_cnt = 0
    total_faboo_cnt = 0
    users_cnt.sort_by {|k, v| -v }.each_with_index{|(acct,cnt),i|
      total_cnt += cnt
      total_faboo_cnt += faboo_cnt[acct]
      if body.length < 420
        body += "🥇 " if i == 0
        body += "🥈 " if i == 1
        body += "🥉 " if i == 2
        body += "🏅 " if i == 3
        body += "🏅 " if i == 4
        # body += ":blank: " if i >= 5
        body += ":@#{acct}:#{sprintf("%4d",cnt)}  "
        body += "\n" if i.modulo(3) == 1 or i <= 4
      end
    }
    body = "📝全体 #{total_cnt} toots\n" + body
    body += "\n#きりランキング #きりぼっと"
    exe_toot(body,visibility = "public",acct = nil,spoiler_text = spoiler_text,rep_id = nil)

    #ニコられランキング
    sleep(60) unless VERB
    spoiler_text = "今日のニコられ数ランキング"
    body = ""
    total_fav_cnt = 0
    fav_acct_cnt.sort_by {|k, v| -v }.each_with_index{|(acct,cnt),i|
      total_fav_cnt += cnt
      if body.length < 420
        body += "🥇 " if i == 0
        body += "🥈 " if i == 1
        body += "🥉 " if i == 2
        body += "🏅 " if i == 3
        body += "🏅 " if i == 4
        # body += ":blank: " if i >= 5
        body += ":@#{acct}:#{sprintf("%4d",cnt)}  "
        body += "\n" if i.modulo(3) == 1 or i <= 4
      end
    }
    body = "📝全体 #{total_fav_cnt} ニコる\n" + body
    body += "\n#きりランキング #きりぼっと"
    exe_toot(body,visibility = "public",acct = nil,spoiler_text = spoiler_text,rep_id = nil)


    sleep(60) unless VERB
    spoiler_text = "今日のニコブ率ランキング"
    body = ""
    faboo_rate.sort_by {|k, v| -v }.each_with_index{|(acct,rate),i|
      # break if i > 10
      break if body.length > 380
      body += "🥇 " if i == 0
      body += "🥈 " if i == 1
      body += "🥉 " if i == 2
      body += "🏅 " if i == 3
      body += "🏅 " if i == 4
      # body += ":blank: " if i >= 5
      # body += ":@#{acct}:#{sprintf("%6.1f",rate)} ％ #{sprintf("%4d",faboo_cnt[acct])}/#{sprintf("%4d",users_cnt[acct])}\n"
      body += ":@#{acct}:#{sprintf("%6.1f",rate)}％  "
      body += "\n" if i.modulo(2) == 0 or i <= 4
    }
    body += "\n※ニコブ率：（ニコられ数＋ブーストされ数）÷トゥート数\n"
    body += "※#{asikiri_d}トゥート未満の人は除外\n#きりランキング #きりぼっと"
    exe_toot(body,visibility = "public",acct = nil,spoiler_text = spoiler_text,rep_id = nil)


    sleep(60) unless VERB
    fav_cnt.sort_by {|k, v| -v }.each_with_index{|(id,cnt),i|
      break if i > 0
      exe_boost(id)
      sleep(5)
      text = statuses_json[id][1]
      f_c = statuses_json[id][2]
      r_c = statuses_json[id][3]
      acct = statuses_json[id][4]
      body = ":@#{acct}:＜「#{text} 」\n#{sprintf("%2d",f_c)}ニコる／#{sprintf("%2d",r_c)}ブースト"
      # body += "\n https://friends.nico/web/statuses/#{id}"
      body += "\n https://friends.nico/@#{acct}/#{id}"
      body += "\n#きりランキング #きりぼっと"
      exe_toot(body,visibility = "public",acct = nil,spoiler_text = "今日最もニコられたトゥートは……",rep_id = nil)
    }

  ############################################################
  # ランキングをトゥート
  when "time2222"
    exe_toot("にゃんにゃんにゃんにゃん！\n₍₍(ฅ=˘꒳ ˘=)ฅ ⁾⁾ ₍₍ ฅ(=╹꒳ ╹=ฅ)⁾⁾",visibility = "public", acct = nil, spoiler_text = nil, rep_id = nil)
  end
end

every(60.minutes, 'hourly1', at: '**:00')    unless VERB
every(1.hours, 'hourly2', at: '**:17')    unless VERB
every(1.day, 'daily1', at: '23:30')      unless VERB
every(1.day, 'daily2', at: '23:55')      unless VERB
every(1.day, 'time2222', at: '22:22')    unless VERB
every(1.week, 'hourly2')   if VERB
# every(1.week, 'hourly1')
