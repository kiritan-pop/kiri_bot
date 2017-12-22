# coding: utf-8
require 'json'
require 'date'
require 'dotenv'
require "eventmachine"
require "faye/websocket"
require 'pp'


# --- config
Dotenv.load
TL='public'
MASTODON_URL = ENV["MASTODON_URL"]
INSTANCE= MASTODON_URL[8..MASTODON_URL.length-1]
TOKEN = ENV["MASTODON_ACCESS_TOKEN"]

MQ_PATH = "mq/"
MQ_FILE_NAME = "mq.json"

# --- debug switch  true false
VERB = false

############################################################
#メイン処理
while(1)do

  EM.run do
      conn = Faye::WebSocket::Client.new(
        "wss://#{INSTANCE}/api/v1/streaming?access_token=#{TOKEN}&stream=#{TL}",
      )

      conn.on :open do |e|
          puts "******************************************"
          puts "connection success."
          pp e
      end

      conn.on :error do |e|
          puts "error occured."
      end

      conn.on :close do |e|
          puts "connection close."
          pp [:close,e.code,e.reason]
          #pp e
          conn = nil
          EM.stop
      end

      conn.on :message do |msg|
        puts "message receive."

  #      Dir.mkdir(JSON_PATH) unless  Dir.exist?(JSON_PATH)
        Dir.mkdir(MQ_PATH) unless  Dir.exist?(MQ_PATH)

        File.open("#{MQ_PATH}#{Time.now.strftime('%Y%m%d%H%M%S')}_#{sprintf("%06d",Time.now.usec)}#{MQ_FILE_NAME}", "w") do |f|
          #puts "******************************************"
          #pp msg
          f.puts(msg.data)
        end

      end
  end

sleep(10)
end
