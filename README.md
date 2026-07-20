# MyDiscopedia

20世紀ヴァイオリン・チェロ奏者のディスコグラフィをまとめた静的Webサイト。
Googleスプレッドシートを原本とし、ビルドスクリプトで静的サイトへ変換して
GitHub Pagesで公開する。

## 構成

```
mydiscopedia/
├── scripts/
│   ├── build.py            # スプレッドシート → docs/data/*.json
│   └── generate_html.py    # docs/data/manifest.json → docs/*.html
├── docs/                    # GitHub Pagesの公開元フォルダ
│   ├── index.html           # 演奏家一覧（トップページ）
│   ├── assets/
│   │   ├── style.css
│   │   └── discography.js   # 検索・絞り込みロジック（全ページ共通）
│   ├── data/
│   │   ├── manifest.json    # 演奏家ごとの件数・年代サマリ
│   │   └── {slug}.json      # 演奏家ごとの録音データ
│   └── performers/
│       └── {slug}.html      # 演奏家ごとのページ
└── .github/workflows/
    └── build.yml            # 自動ビルド・公開ワークフロー
```

## ローカルでのビルド（開発用）

Excelファイルから直接ビルドする場合:

```bash
cd scripts
python3 build.py --xlsx /path/to/MyDiscopedia.xlsx
python3 generate_html.py
```

`docs/` フォルダの中身が更新される。ブラウザで直接確認する場合は
`fetch()` を使っているため、`file://` では動かないことがある。
簡易サーバーを立てて確認すること:

```bash
cd docs
python3 -m http.server 8000
# ブラウザで http://localhost:8000 を開く
```

## 本番ビルド（公開されたGoogleスプレッドシートから）

`/gviz/tq` 形式のCSVエクスポートは、列ごとに型を自動推測し、その型に
合わない値（例: `1962/06` のような不完全な日付）を空欄にしてしまう
既知の癖がある。これを避けるため、各シートタブのGID（数値ID）を
指定して、生のセル内容をそのまま取得する方式を使う。

```bash
python3 scripts/build.py --sheet-id "【スプレッドシートのID】" --gids scripts/gids.json
python3 scripts/generate_html.py
```

`scripts/gids.json` に、演奏家スラッグ→シートタブのGIDのマッピングを
あらかじめ記述しておく。GIDは、各シートタブを開いたときのURL末尾
`#gid=123456789` の数字部分。タブの並び替えをしても既存タブのGIDは
変わらないが、新しいシートを追加した場合はここに追記が必要。

```json
{
  "stern": "1372978077",
  "szeryng": "58797465",
  ...
}
```

## データポリシー

- 各演奏家シートで **ComposerまたはWorkが空の行はスキップ**する
  （放送記録はあるが曲目不詳、などのケースを除外するため）。
- Notes列に "live" という文字列が含まれる場合、ライヴ録音として扱う。
- Date列は表示用の元の文字列と、ソート用に正規化した日付
  （`YYYY-MM-DD`）の両方を保持する。

## GitHub Actionsによる自動更新

`.github/workflows/build.yml` が、スプレッドシートの公開データから
定期的に（またはワークフロー手動実行で）サイトを再生成し、
変更があれば自動的にコミット・公開する。

事前に、リポジトリの Settings → Secrets and variables → Actions →
Variables で `SHEET_ID` という名前の変数に、スプレッドシートのID
（URLの `/d/` と `/edit` の間の文字列）を設定しておくこと。
`scripts/gids.json` はリポジトリに含まれているので追加設定は不要。
