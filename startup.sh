#!/bin/bash
# キャッシュディレクトリをクリア
rm -rf src/utils/__pycache__
rm -rf src/__pycache__

# Streamlitを本番モードで起動（CORS設定を明示的に指定）
streamlit run src/app.py --server.port 8000 --server.fileWatcherType none --server.runOnSave false --server.headless true --server.enableCORS true --server.enableXsrfProtection true
