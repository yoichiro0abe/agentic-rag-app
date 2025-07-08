#!/bin/bash
# キャッシュディレクトリをクリア
rm -rf src/utils/__pycache__
rm -rf src/__pycache__

# デバッグ: 環境情報を確認
echo "=== Environment Debug ==="
echo "Current directory: $(pwd)"
echo "Python path: $(which python)"
echo "Pip path: $(which pip)"
ls -la

# デバッグ: パッケージバージョンを確認
echo "=== Package Versions Debug ==="
pip show opentelemetry-semantic-conventions
echo "=== Python Version ==="
python --version
echo "=== Environment Info ==="
pip list | grep opentelemetry

# ローカルと同じバージョンに固定
pip install --force-reinstall opentelemetry-semantic-conventions==0.55b1

# 再度確認
echo "=== After Fix ==="
pip show opentelemetry-semantic-conventions

# Streamlitを本番モードで起動（CORS設定を明示的に指定）
streamlit run src/app.py --server.port 8000 --server.fileWatcherType none --server.runOnSave false --server.headless true --server.enableCORS true --server.enableXsrfProtection true
