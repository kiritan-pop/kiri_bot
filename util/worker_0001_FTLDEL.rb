# coding: utf-8
require 'mastodon'
require 'nokogiri'
require 'json'
require 'highline/import'
require 'oauth2'
require 'dotenv'
require 'pp'
require "fileutils"

# --- config
Dotenv.load
MASTODON_URL = ENV["MASTODON_URL"]
INSTANCE= MASTODON_URL[8..MASTODON_URL.length-1]
TOKEN = ENV["MASTODON_ACCESS_TOKEN"]

MQ_PATH = "mq/"
MQ_PATH_AFT = "mq_0001/"
MQ_FILE_NAME = "mq.json"

# --- debug switch  true false
VERB = false


############################################################
#メイン処理

puts "処理開始ー！"

while true do

  puts "ループ中"  if VERB

  Dir.glob("#{MQ_PATH}*#{MQ_FILE_NAME}").sort.each{|file_path|
    begin

        puts "##このファイルの処理中 #{file_path} ############" 

        msg_data = {}
        File.open(file_path, "r") do |f| 
          msg_data = f.read
        end

        pp msg_data  if VERB
        toot = JSON.parse(msg_data)

        case toot["event"] 
#          when "notification"     # publicのTLには含まれないので無視！
          when  "update"
            body = JSON.parse(toot["payload"])
            contents = Nokogiri::HTML.parse(body["content"])

            #同一インスタンスの人のみ
            if body["account"]["acct"].match("@") ==nil
              Dir.mkdir(MQ_PATH_AFT) unless  Dir.exist?(MQ_PATH_AFT)
#              File.rename(file_path,MQ_PATH_AFT + file_path.split("/")[1] )
              FileUtils.mv(file_path, MQ_PATH_AFT + file_path.split("/")[1])  
            else
              #処理したファイルは消す（移動）
              File.delete(file_path)
            end


#          when "delete"  #一応取っておく！
#            Dir.mkdir(MQ_PATH_AFT) unless  Dir.exist?(MQ_PATH_AFT)
#            File.rename(file_path,MQ_PATH_AFT + file_path.split("/")[1] )
#            FileUtils.mv(file_path, MQ_PATH_AFT + file_path.split("/")[1])  
        
          else
            #処理したファイルは消す
            File.delete(file_path)

        end
        
    rescue => e
      puts "error "
      puts e
        Dir.mkdir("del/") unless  Dir.exist?("del/")
 #       File.rename(file_path,"del/"+file_path.split("/")[1] )
        FileUtils.mv(file_path, "del/"+file_path.split("/")[1])  
    end

  }

  sleep(10)

end