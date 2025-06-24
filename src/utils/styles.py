"""
チャットボットアプリケーション用のCSSスタイル
"""


def get_custom_css():
    return """
    <style>
    /* メインのカスタムスタイル */
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
    }

    /* サイドバーのスタイル */
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
    }

    /* ボタンのスタイル */
    .stButton > button {
        width: 100%;
        border-radius: 20px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }

    /* チャットメッセージのスタイル */
    .chat-message {
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        animation: fadeIn 0.5s ease-in;
    }

    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin-left: 20%;
    }

    .assistant-message {
        background: #f1f3f4;
        color: #333;
        margin-right: 20%;
    }

    /* アニメーション */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* プロンプト一覧のスタイル */
    .prompt-card {
        background: white;
        border: 1px solid #e1e5e9;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }

    .prompt-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }

    /* 検索ボックスのスタイル */
    .search-box {
        background: white;
        border: 2px solid #667eea;
        border-radius: 25px;
        padding: 0.5rem 1rem;
        font-size: 1rem;
    }

    .search-box:focus {
        outline: none;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }

    /* 統計情報のスタイル */
    .metric-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin: 0.5rem 0;
    }

    /* フォームのスタイル */
    .custom-form {
        background: #f8f9fa;
        padding: 2rem;
        border-radius: 15px;
        border: 1px solid #e9ecef;
    }

    /* テーブルのスタイル */
    .dataframe tbody tr:hover {
        background-color: #f5f5f5;
    }

    /* ローディングアニメーション */
    .loading {
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 3px solid #f3f3f3;
        border-top: 3px solid #667eea;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    /* レスポンシブデザイン */
    @media (max-width: 768px) {
        .user-message, .assistant-message {
            margin-left: 0;
            margin-right: 0;
        }

        .main-header {
            padding: 0.5rem;
            font-size: 1.2rem;
        }
    }

    /* カスタムアラート */
    .custom-success {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }

    .custom-warning {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }

    .custom-info {
        background: linear-gradient(135deg, #00c6ff 0%, #0072ff 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    </style>
    """
