# Instagram Competitor Analyzer (SocialBlade 風)

InstagramのプロフィールURL（またはユーザー名）を入力すると、以下を表示するWebアプリです。

- 直近投稿の平均いいね数
- 直近投稿の平均コメント数
- エンゲージメント率（`(平均いいね + 平均コメント) / フォロワー * 100`）
- 投稿ごとのいいね/コメント
- フォロワー増加数（**このアプリで前回取得したスナップショットとの差分**）

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

ブラウザで `http://localhost:5000` を開いてください。

## 注意点

- 公開アカウント向けです。
- Instagram側の仕様変更・レート制限・ログイン要件により取得できない場合があります。
- ログインセッションが必要な場合は環境変数 `INSTAGRAM_SESSIONID` を設定してください。
- フォロワー増加数はInstagram公式の時系列APIではなく、ローカルDBに保存した前回値との差分です。
