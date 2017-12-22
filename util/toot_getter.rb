# coding: utf-8
require 'mastodon'
require 'json'
require 'dotenv'
require 'pp'
require 'sqlite3'

# --- config
Dotenv.load

# ---
LTL_PATH = "mq_0001test/"
#USER_PATH = "Daily_#{Time.now.strftime('%Y%m%d')}/"

# --- debug switch  true false
VERB = true

############################################################
#トゥートメソッド
def exe_get(max_id = nil)
  #おまじないー！
  client = Mastodon::REST::Client.new(base_url: ENV["MASTODON_URL"],
                                      bearer_token: ENV["MASTODON_ACCESS_TOKEN"])

  if max_id == nil
    return client.public_timeline({:limit => 40,:local => true})
  else
    return client.public_timeline({:limit => 40,:max_id => max_id,:local => true})
  end

end

############################################################
#メイン処理
id = 0
i = 0
j = 0
#スタートｉｄ取得
File.open('.tgrc', "r") do |f|
  id = f.read.to_i
end

while true do
  statuses = exe_get(id)
  #pp statuses
  #sleep(600)
  statuses.each{|status|
    #pp status
    id = status.id.to_i
    content = status.content
    tmp_dt = Time.parse(status.created_at).localtime
    date = tmp_dt.strftime('%Y%m%d')
    time = tmp_dt.strftime('%H%M%S')
    acct = status.account.acct
    display_name = status.account.display_name

    media_attachments = ""
    status.media_attachments.each{|media|
      media_attachments += media.url + " "
    }

    if acct.match("@") ==nil

      #pp tmp_dt,date,time
      #pp id, content,  acct, display_name,media_attachments

      begin
        db = SQLite3::Database.new('db/statuses.db',{:timeout => 6000})
        #{id},#{date.to_i},#{time.to_i},#{content},#{acct},#{display_name},#{media_attachments})"
        db.execute("insert into statuses (id,date,time,content,acct,display_name,media_attachments) values (?,?,?,?,?,?,?)",
                    id, date.to_i, time.to_i, content, acct, display_name, media_attachments)
        j += 1
      rescue => e
        pp "INSERT ERROR!",e
        File.open('geterr.txt', "a") do |f|
          f.puts("#{id}@@@@@#{date}@@@@@#{time}@@@@@#{content}@@@@@#{acct}@@@@@#{display_name}@@@@@#{media_attachments}")
        end
      end
      db.close
    end

    #取得したid格納（続きをやるため）
    #sleep(600)
    if  i.modulo(100) == 0
      File.open('.tgrc', "w") do |f|
        puts "#{j}/#{i}件目:#{id}:#{date}:#{time}"
        f.puts(id)
      end
    end
    i += 1
  }
  sleep(1.4)
end
