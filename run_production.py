"""
Project S.M.I.L.E. - Production Server Runner
Runs the application using high-performance, multi-threaded Waitress WSGI server.
"""
import os
import sys
from waitress import serve
from app import app
import smile_config

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    threads = int(os.environ.get('THREADS', 8))
    
    print("\n" + "="*70)
    print("   PROJECT S.M.I.L.E. - PRODUCTION SERVER (WAITRESS)")
    print(f"   School: {smile_config.SCHOOL_NAME}")
    print(f"   Listening on: http://0.0.0.0:{port} ({threads} worker threads)")
    print(f"   Ready for public internet traffic & gate biometric streaming")
    print("="*70 + "\n")
    
    serve(app, host='0.0.0.0', port=port, threads=threads)
