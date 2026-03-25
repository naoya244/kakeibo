import http.server
import os
import sys

port = int(os.environ.get('PORT', 8080))
directory = os.path.dirname(os.path.abspath(__file__))
os.chdir(directory)

handler = http.server.SimpleHTTPRequestHandler
httpd = http.server.HTTPServer(('', port), handler)
print(f'Serving on port {port}')
httpd.serve_forever()
