"""
Unified Healthcare System Server
Runs the API server and serves the web UI.
Run this script and open http://localhost:8000/unified_healthcare_ui.html in your browser.
"""

# CONFIG
HTML_PORT = 8000
API_PORT = 5000
HTML_FILE = "unified_healthcare_ui.html"

import http.server
import os
import socketserver
import webbrowser
import threading
import time
from pathlib import Path


class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()


def start_html_server():
    """Start the HTML file server"""
    web_dir = Path(__file__).parent
    os.chdir(web_dir)
    
    handler = MyHTTPRequestHandler
    
    try:
        with socketserver.TCPServer(("localhost", HTML_PORT), handler) as httpd:
            url = f"http://localhost:{HTML_PORT}/{HTML_FILE}"
            print(f"✓ HTML server running at {url}")
            httpd.serve_forever()
    except OSError as e:
        if e.errno == 10048:  # Address already in use
            print(f"✗ Port {HTML_PORT} is already in use. Please close the other application or change HTML_PORT in CONFIG.")
        else:
            raise


def start_api_server():
    """Start the API server"""
    import unified_healthcare_api
    unified_healthcare_api.app.run(
        host="localhost", 
        port=API_PORT, 
        debug=False, 
        use_reloader=False
    )


def main():
    """Start both servers"""
    print("=" * 70)
    print("🏥 Unified Healthcare System")
    print("=" * 70)
    print(f"\nStarting servers...")
    print(f"📄 HTML Server: http://localhost:{HTML_PORT}/{HTML_FILE}")
    print(f"🔌 API Server: http://localhost:{API_PORT}")
    print(f"\n⚠️  Make sure the following are set up:")
    print(f"   1. Trained NER model in models/symptom_ner_spacy/")
    print(f"   2. FAISS indices in diag/ folder (run diag/embedding.py first)")
    print(f"   3. All dependencies installed (pip install -r requirements.txt)")
    print(f"\nPress Ctrl+C to stop all servers\n")
    
    # Start API server in a separate thread
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()
    
    # Give API server a moment to start
    time.sleep(3)
    
    # Start HTML server in a separate thread
    html_thread = threading.Thread(target=start_html_server, daemon=True)
    html_thread.start()
    
    # Give HTML server a moment to start
    time.sleep(2)
    
    # Open browser
    url = f"http://localhost:{HTML_PORT}/{HTML_FILE}"
    print(f"\n🌐 Opening browser at {url}...")
    webbrowser.open(url)
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down servers...")
        print("✓ Servers stopped.")


if __name__ == "__main__":
    main()

