# coding: utf-8
require 'mastodon'
require 'nokogiri'
require 'json'
require 'highline/import'
require 'dotenv'
require 'pp'
require 'clockwork'
require 'fileutils'
require 'sqlite3'
include Clockwork


# --- config
Dotenv.load

# ---
LTL_PATH = "mq_0001/"
LTL_PATH_AFT = "mq_0002/"
DB_PATH = "db/statuses.db"
#USER_PATH = "Daily_#{Time.now.strftime('%Y%m%d')}/"


# --- debug switch  true false
VERB = false

############################################################
#ユーザ
class User
  def initialize(username)
    @user_name = username
    @user_data = {}

    Dir.mkdir(USER_PATH) unless  Dir.exist?(USER_PATH)
    Dir.mkdir("#{USER_PATH}user/") unless  Dir.exist?("#{USER_PATH}user/")

    if File.exist?("#{USER_PATH}user/#{@user_name}.json") == false
      File.open("#{USER_PATH}user/#{@user_name}.json",'w') do |io|
        JSON.dump({},io)
      end
    else
      @user_data = open("#{USER_PATH}user/#{@user_name}.json") do |io|
        JSON.load(io)
      end
    end
  end

  def set(key,val)
    if @user_data[key] == nil
      @user_data[key] = val
    else
      @user_data[key] += val
    end
  end

  def save()
    File.open("#{USER_PATH}user/#{@user_name}.json",'w') do |io|
      #pp @user_data
      JSON.dump(@user_data,io)
    end

  end

end

############################################################
#セット処理
def sum(username,category,score)

  return if score == nil || score == 0
  if File.exist?("#{USER_PATH}ranking/#{category}.json") == false
    File.open("#{USER_PATH}ranking/#{category}.json",'w') do |io|
      io.puts(JSON.generate({}))
    end
  end
  cat = {}
  File.open("#{USER_PATH}ranking/#{category}.json", "r") do |io|
    data = io.read
    cat = JSON.parse(data)
  end
  File.open("#{USER_PATH}ranking/#{category}.json", "w") do |io|
    cat[username] = score
    JSON.dump(cat,io)
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
  puts "#{body},#{acct},#{visibility},#{spoiler_text},#{rep_id}"    if VERB
  client.create_status_kiri( "#{body[0,460]}#{acct}" , visibility ,spoiler_text,rep_id)  unless VERB
end

############################################################
#ランキングメソッド
def ranking(category,toot_cnt)
  File.open("#{USER_PATH}ranking/#{category}.json", "r") do |f|
    data = f.read
    ranking = JSON.parse(data)
    disp_cat = ""
    case category
    when "ero"
      disp_cat = "💗エロ部門"
    when "kitanai"
      disp_cat = "💩きたない部門"
    when "aho"
      disp_cat = "🤣あほ部門"
    when "nicoru"
      disp_cat = ":nicoru:ニコる君部門"
    when "enquete"
      disp_cat = "📊アンケート使い部門"
    when "momona"
      disp_cat = ":@JC:ももな部門"
    when "meimei"
      disp_cat = ":@mei23:めいめい部門"
    when "chahan"
      disp_cat = "🍚チャーハン部門"
    when "aisatsu"
      disp_cat = "🙋あいさつ部門"
    when "nyan"
      disp_cat = "🐾にゃーん部門"
    when "wakaru"
      disp_cat = "😘わかるオタク部門"
    end

    i = 1
    body = "📝#{toot_cnt}toot/💁#{ranking.size}人\n"
    ranking.sort_by{|a,b| -b.to_f }.each do|k,v|
      next if v == nil
      next if i > 18
      body += "🥇" if i == 1
      body += "🥈" if i == 2
      body += "🥉" if i == 3
      body += ":@#{k}: #{sprintf("%3d", v )} "
      body += "\n" if i <= 3 || i.modulo(3) == 0

      i += 1
    end
      exe_toot(body+"\n #きりたん勝手にランキング #きりぼっと",visibility = "public",acct = nil,spoiler_text = "きりたんの勝手にランキング#{disp_cat}・デイリー",rep_id = nil)

  end
end

############################################################
#メイン処理
handler do |job|
  case job
  when "main"
    ############################################################
    #メイン処理１ トゥート集計範囲
    puts "集計開始ー"
    DATE = Time.now.strftime('%Y%m%d')
    USER_PATH = "Daily_#{DATE}/"

    user_data = {}
    toot_cnt = 0
    Dir.mkdir(USER_PATH) unless  Dir.exist?(USER_PATH)

    db = SQLite3::Database.new('db/statuses.db')
    sql = "select acct,content from statuses where date = #{DATE} "
    db.execute(sql)  { |acct,content|
      toot_cnt += 1
      contents = Nokogiri::HTML.parse(content)
      text = ''
      contents.search('p').children.each do |item|
        text += item.text.strip if item.text?
      end
      next if text == ""
      username = acct

      #ユーザ情報読み込み！
      if user_data[username] == nil
        user_data[username] = User.new(username)
      end

      #######解析処理だよ！
      user_data[username].set("count",1)  #トゥーカウント
      user_data[username].set("ero",1) if text.match(/ちん[ちこぽ]|まんこ|おまんちん|ﾁﾝｺ|ﾏﾝｺ|ㄘんㄘん|膣|おっぱい|早漏|[パぱ][こコ]|[しシ][こコ][っれろてりるしシ]|デリヘル|クンニ|勃起|[まマちチ][んン]毛|精子|射精|セックス|おせっせ|クリトリス|フェラ|乳首|尻|アナル|あなる|騎乗位|精液|ちくび|陰茎|ペニス|マン汁/) !=nil
      user_data[username].set("kitanai",1) if text.match(/うん[こち]|ﾘﾌﾞﾘﾌﾞ|[くク][そソ]|おしっこ|糞/) !=nil
      user_data[username].set("momona",1) if text.match("ももな") !=nil
      user_data[username].set("meimei",1) if text.match("めいめい") !=nil
      user_data[username].set("chahan",1) if text.match(/チャーハン|炒飯/) !=nil
      user_data[username].set("aho",1) if text.size <= 3   #３文字以下
      user_data[username].set("aho",1) if text.gsub(/\p{Hiragana}/,"") == "" #ひらがなのみ
      user_data[username].set("nicoru",1) if text.match(":nicoru") !=nil #にこる君
      user_data[username].set("enquete",1) if text.match("friends.nico アンケート") !=nil #にこる君
      user_data[username].set("aisatsu",1) if text.match(/おはよ|..あり|こんにち|こんばん|ただいま|おやすみ|おかえり|ありがと|てら/) !=nil
      user_data[username].set("nyan",1) if text.match(/にゃ[ー〜]ん|にぇ[ー〜]ん/) !=nil
      user_data[username].set("wakaru",1) if text.match(/わかる$/) !=nil

      #######保存処理だよ！
      user_data[username].save()

    }
    db.close
    puts "トゥート件数:#{toot_cnt}"
    #sleep(60)
    ############################################################
    #メイン処理２ スコア計算
    puts "スコア計算開始ー！"

    Dir.glob("#{USER_PATH}user/*.json").each{|file_path|
      #pp file_path

      user_data = {}
      File.open(file_path, "r") do |f|
        data = f.read
        user_data = JSON.parse(data)
      end
      next if user_data["count"].to_i < 30 #トゥート未満はスキップ

      user_score = {}
      user_score["ero"] = user_data["ero"].to_f / user_data["count"].to_f * 1000             if user_data["ero"] !=nil
      user_score["kitanai"] = user_data["kitanai"].to_f / user_data["count"].to_f * 1000     if user_data["kitanai"] !=nil
      user_score["momona"] = user_data["momona"].to_f / user_data["count"].to_f * 1000       if user_data["momona"] !=nil
      user_score["meimei"] = user_data["meimei"].to_f / user_data["count"].to_f * 1000       if user_data["meimei"] !=nil
      user_score["chahan"] = user_data["chahan"].to_f / user_data["count"].to_f * 1000       if user_data["chahan"] !=nil
      user_score["aho"] = user_data["aho"].to_f / user_data["count"].to_f * 1000             if user_data["aho"] !=nil
      user_score["nicoru"] = user_data["nicoru"].to_f / user_data["count"].to_f * 1000       if user_data["nicoru"] !=nil
      user_score["enquete"] = user_data["enquete"].to_f / user_data["count"].to_f * 1000     if user_data["enquete"] !=nil
      user_score["aisatsu"] = user_data["aisatsu"].to_f / user_data["count"].to_f * 1000     if user_data["aisatsu"] !=nil
      user_score["nyan"] = user_data["nyan"].to_f / user_data["count"].to_f * 1000           if user_data["nyan"] !=nil
      user_score["wakaru"] = user_data["wakaru"].to_f / user_data["count"].to_f * 1000       if user_data["wakaru"] !=nil

      next if user_score == {}

      Dir.mkdir("#{USER_PATH}score/") unless  Dir.exist?("#{USER_PATH}score/")
      File.open("#{USER_PATH}score/#{file_path.split("/")[2]}",'w') do |io|
        JSON.dump(user_score,io)
      end

    }

    ############################################################
    #メイン処理３ カテゴリ別集計
    puts "集計開始ー！"

    Dir.glob("#{USER_PATH}score/*.json").each{|file_path|
      #pp file_path
      Dir.mkdir("#{USER_PATH}ranking/") unless  Dir.exist?("#{USER_PATH}ranking/")

      user_score = {}
      File.open(file_path, "r") do |f|
        data = f.read
        user_score = JSON.parse(data)
      end

      username = file_path.split("/")[2].split(".")[0]
      sum(username,"ero",user_score["ero"])
      sum(username,"kitanai",user_score["kitanai"])
      sum(username,"momona",user_score["momona"])
      sum(username,"meimei",user_score["meimei"])
      sum(username,"chahan",user_score["chahan"])
      sum(username,"aho",user_score["aho"])
      sum(username,"nicoru",user_score["nicoru"])
      sum(username,"enquete",user_score["enquete"])
      sum(username,"aisatsu",user_score["aisatsu"])
      sum(username,"nyan",user_score["nyan"])
      sum(username,"wakaru",user_score["wakaru"])

    }

    ############################################################
    #メイン処理４
    puts "ランキング発表ー！"

    ranking("aisatsu",toot_cnt)
    sleep(90)     unless VERB
    ranking("enquete",toot_cnt)
    sleep(90)     unless VERB
    ranking("nicoru",toot_cnt)
    sleep(90)     unless VERB
    ranking("momona",toot_cnt)
    sleep(90)     unless VERB
    ranking("meimei",toot_cnt)
    sleep(90)     unless VERB
    ranking("nyan",toot_cnt)
    sleep(90)     unless VERB
    ranking("ero",toot_cnt)
    sleep(90)     unless VERB
    ranking("kitanai",toot_cnt)
    sleep(90)     unless VERB
    ranking("aho",toot_cnt)
    sleep(90)     unless VERB
    ranking("wakaru",toot_cnt)
    sleep(90)     unless VERB
    ranking("chahan",toot_cnt)
  end
end

every(1.day, 'main', at: '22:30')      unless VERB
every(1.week, 'main')   if VERB
#every(1.week, 'main')
