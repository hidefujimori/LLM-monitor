# LLM Monitor

OllamaとGPUの情報をSplunk HEC経由でLAN上のSplunkに送信し、ダッシュボードで可視化するモニタリングツールです。

## 機能

- **Ollamaモニタリング**: インストール済みモデル一覧、実行中モデル、バージョン情報を収集
- **GPUモニタリング**: NVIDIA / AMD GPU の使用率、VRAM、温度、電力消費を収集
- **Splunk HEC送信**: 収集データをLAN上のSplunkへリアルタイム送信
- **Splunkダッシュボード**: 収集データを時系列グラフ・テーブルで可視化

## アーキテクチャ

```
[LLM Machine]                    [LAN]           [Splunk Server]
  Ollama API  ─┐
               ├─> collector ──(HEC)──> Splunk Index ──> Dashboard
  nvidia-smi  ─┘
```

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. 設定ファイルの準備

```bash
cp config/config.yaml.example config/config.yaml
```

`config/config.yaml` を編集して以下を設定します：

| 設定項目 | 説明 |
|---------|------|
| `splunk.hec_url` | Splunk HEC エンドポイント URL |
| `splunk.hec_token` | Splunk HEC トークン |
| `splunk.index` | 送信先インデックス名 |
| `ollama.base_url` | Ollama API URL（デフォルト: `http://localhost:11434`）|
| `collection.interval_seconds` | 収集間隔（秒） |
| `collection.gpu_enabled` | GPU収集の有効/無効 |

### 3. Splunk の設定

#### インデックス作成

`splunk/indexes.conf` を Splunk サーバーの以下のパスにコピーします：

```
$SPLUNK_HOME/etc/system/local/indexes.conf
```

#### HEC の有効化

`splunk/inputs.conf` を参考に、Splunk Web UI から HEC トークンを作成します：

1. Splunk Web → Settings → Data Inputs → HTTP Event Collector
2. **Global Settings** で HEC を有効化
3. **New Token** でトークンを作成（index: `llm_monitor`）
4. 生成されたトークンを `config/config.yaml` の `splunk.hec_token` に設定

#### ダッシュボードのインポート

1. Splunk Web → Search & Reporting → Dashboards → Create New Dashboard
2. **Edit Source** を選択し `splunk/dashboard.xml` の内容を貼り付けて保存

### 4. コレクターの起動

```bash
cd collector
python main.py
```

環境変数でコンフィグパスを指定することもできます：

```bash
CONFIG_PATH=/path/to/config.yaml python main.py
```

## データ仕様

### Ollama メトリクス (`metric_type=ollama`)

```json
{
  "metric_type": "ollama",
  "status": "running",
  "version": "0.5.4",
  "model_count": 3,
  "models": [...],
  "running_model_count": 1,
  "running_models": [...]
}
```

### GPU メトリクス (`metric_type=gpu`)

```json
{
  "metric_type": "gpu",
  "gpu_count": 1,
  "total_vram_mb": 24576,
  "used_vram_mb": 8192,
  "free_vram_mb": 16384,
  "gpus": [...]
}
```

## ファイル構成

```
LLM-monitor/
├── collector/
│   ├── main.py              # エントリーポイント・メインループ
│   ├── ollama_collector.py  # Ollama API からメトリクス収集
│   ├── gpu_collector.py     # nvidia-smi / rocm-smi からGPU情報収集
│   └── splunk_hec.py        # Splunk HEC への送信クライアント
├── splunk/
│   ├── indexes.conf         # Splunkインデックス設定
│   ├── inputs.conf          # Splunk HEC入力設定
│   └── dashboard.xml        # Splunkダッシュボード定義
├── config/
│   ├── config.yaml          # 実行時設定（gitignore済み）
│   └── config.yaml.example  # 設定テンプレート
├── requirements.txt
└── README.md
```

## 動作要件

- Python 3.10+
- Ollama（ローカルLLMマシン上）
- nvidia-smi（NVIDIAの場合）または rocm-smi（AMDの場合）
- Splunk Enterprise / Splunk Cloud（LAN上）
