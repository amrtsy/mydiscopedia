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

## 本番ビルド（公開されたGoogleスプレッドシートCSVから）

```bash
python3 scripts/build.py --csv-base "https://docs.google.com/spreadsheets/d/【シートID】/gviz/tq?tqx=out:csv&sheet="
python3 scripts/generate_html.py
```

`--csv-base` の末尾にシート名（Stern, Szeryng, Du Pre など）が
自動的に付加されてCSVを取得する。

## データポリシー

- 各演奏家シートで **ComposerまたはWorkが空の行はスキップ**する
  （放送記録はあるが曲目不詳、などのケースを除外するため）。
- Notes列に "live" という文字列が含まれる場合、ライヴ録音として扱う。
- Date列は表示用の元の文字列と、ソート用に正規化した日付
  （`YYYY-MM-DD`）の両方を保持する。

## GitHub Actionsによる自動更新

`.github/workflows/build.yml` が、スプレッドシートの公開CSVから
定期的に（またはワークフロー手動実行で）サイトを再生成し、
変更があれば自動的にコミット・公開する。

事前に、リポジトリの Settings → Secrets and variables → Actions →
Variables で `SHEET_CSV_BASE` という名前の変数に、上記の
`--csv-base` に渡すURLを設定しておくこと。
