#!/usr/bin/env ruby

require 'mastodon'
require 'highline/import'
require 'oauth2'
require 'dotenv'
require 'pp'

DEFAULT_APP_NAME = "kiri_bot made by @kiritan"
DEFAULT_MASTODON_URL = 'https://friends.nico'
FULL_ACCESS_SCOPES = "read write follow"

Dotenv.load

if !ENV["MASTODON_URL"]
  ENV["MASTODON_URL"] = ask("Instance URL: "){|q| q.default = DEFAULT_MASTODON_URL}
  File.open(".env", "a+") do |f|
    f.write "MASTODON_URL = '#{ENV["MASTODON_URL"]}'\n"
  end
end

scopes = ENV["MASTODON_SCOPES"] || FULL_ACCESS_SCOPES
app_name = ENV["MASTODON_APP_NAME"] || DEFAULT_APP_NAME

if !ENV["MASTODON_CLIENT_ID"] || !ENV["MASTODON_CLIENT_SECRET"]
  client = Mastodon::REST::Client.new(base_url: ENV["MASTODON_URL"])
  app = client.create_app(app_name, "urn:ietf:wg:oauth:2.0:oob", scopes)
  ENV["MASTODON_CLIENT_ID"] = app.client_id
  ENV["MASTODON_CLIENT_SECRET"] = app.client_secret
  File.open(".env", "a+") do |f|
    f.write "MASTODON_CLIENT_ID = '#{ENV["MASTODON_CLIENT_ID"]}'\n"
    f.write "MASTODON_CLIENT_SECRET = '#{ENV["MASTODON_CLIENT_SECRET"]}'\n"
  end
end

if !ENV["MASTODON_ACCESS_TOKEN"]
  client = OAuth2::Client.new(ENV["MASTODON_CLIENT_ID"],
                              ENV["MASTODON_CLIENT_SECRET"],
                              site: ENV["MASTODON_URL"])
  login_id = ask("Your Account: ")
  password = ask("Your Password: "){|q| q.echo = "*"}
  token = client.password.get_token(login_id, password, scope: scopes)
  ENV["MASTODON_ACCESS_TOKEN"] = token.token
  File.open(".env", "a+") do |f|
    f.write "MASTODON_ACCESS_TOKEN = '#{ENV["MASTODON_ACCESS_TOKEN"]}'\n"
  end
end

client = Mastodon::REST::Client.new(base_url: ENV["MASTODON_URL"],
                                    bearer_token: ENV["MASTODON_ACCESS_TOKEN"])

## 投稿する
message = ARGV[0] || ask("Your Message: ")
response = client.create_status(message)

## とりあえず結果を出力してみる
pp response

