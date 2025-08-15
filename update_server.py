"""
Simple update server for IDF Reader application.
This is a basic implementation - in production you'd use a proper web server.
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from version import get_version, compare_versions

class UpdateHandler(BaseHTTPRequestHandler):
    """HTTP handler for update requests."""
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/check_update':
            self.handle_check_update(parse_qs(parsed_path.query))
        elif parsed_path.path == '/api/download':
            self.handle_download(parse_qs(parsed_path.query))
        else:
            self.send_error(404, "Not Found")
    
    def handle_check_update(self, params):
        """Handle update check requests."""
        try:
            current_version = params.get('current_version', [''])[0]
            channel = params.get('channel', ['stable'])[0]
            platform = params.get('platform', [''])[0]
            
            # In a real implementation, you'd check your database/file system
            # for the latest version based on channel and platform
            latest_version = "1.1.0"  # This would come from your version database
            
            # Check if update is available
            update_available = compare_versions(current_version, latest_version) < 0
            
            response = {
                "update_available": update_available,
                "version": latest_version if update_available else current_version,
                "download_url": f"http://localhost:8000/api/download?version={latest_version}&platform={platform}" if update_available else None,
                "release_notes": "• שיפור ביצועים\n• תיקון באגים\n• תכונות חדשות" if update_available else "",
                "file_size": 50 * 1024 * 1024,  # 50MB example
                "checksum": "abc123def456",  # MD5 or SHA256 checksum
                "required": False,  # Whether this is a mandatory update
                "release_date": "2024-01-15T10:30:00Z"
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
            
        except Exception as e:
            self.send_error(500, f"Internal Server Error: {e}")
    
    def handle_download(self, params):
        """Handle file download requests."""
        try:
            version = params.get('version', [''])[0]
            platform = params.get('platform', [''])[0]
            
            # In a real implementation, you'd serve the actual update file
            # For now, we'll just return a placeholder response
            
            # Example: serve a file from updates directory
            # update_file = f"updates/idf-reader-{version}-{platform}.exe"
            # if os.path.exists(update_file):
            #     with open(update_file, 'rb') as f:
            #         content = f.read()
            #     
            #     self.send_response(200)
            #     self.send_header('Content-Type', 'application/octet-stream')
            #     self.send_header('Content-Disposition', f'attachment; filename="idf-reader-{version}.exe"')
            #     self.send_header('Content-Length', str(len(content)))
            #     self.end_headers()
            #     self.wfile.write(content)
            # else:
            #     self.send_error(404, "Update file not found")
            
            # For demo purposes, return an error
            self.send_error(501, "File downloads not implemented in demo server")
            
        except Exception as e:
            self.send_error(500, f"Internal Server Error: {e}")
    
    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[UPDATE SERVER] {format % args}")

def run_update_server(port=8000):
    """Run the update server."""
    try:
        server = HTTPServer(('localhost', port), UpdateHandler)
        print(f"Update server running on http://localhost:{port}")
        print("Available endpoints:")
        print(f"  - Check updates: http://localhost:{port}/api/check_update?current_version=1.0.0&channel=stable&platform=win32")
        print(f"  - Download: http://localhost:{port}/api/download?version=1.1.0&platform=win32")
        print("\nPress Ctrl+C to stop the server")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down update server...")
        server.shutdown()
    except Exception as e:
        print(f"Error starting update server: {e}")

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_update_server(port)