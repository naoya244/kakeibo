# encoding: utf-8
require 'webrick'

ENV['LANG'] = 'en_US.UTF-8'

doc_root = File.dirname(File.expand_path(__FILE__))

server = WEBrick::HTTPServer.new(
  Port: Integer(ENV['PORT'] || 8080),
  DocumentRoot: doc_root,
  Logger: WEBrick::Log.new($stderr, WEBrick::Log::INFO),
  AccessLog: [[File.open(File::NULL, 'w'), WEBrick::AccessLog::COMMON_LOG_FORMAT]]
)

# Serve index.html explicitly to avoid encoding issues
server.mount_proc '/' do |req, res|
  path = File.join(doc_root, 'index.html')
  res.body = File.read(path, encoding: 'UTF-8')
  res['Content-Type'] = 'text/html; charset=utf-8'
end

trap('INT') { server.shutdown }
trap('TERM') { server.shutdown }
server.start
