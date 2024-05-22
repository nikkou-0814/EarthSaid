# Earth Said BOT

<div style="text-align: center;">
    <img src="screenshot.png" alt="Kyoshin Report BOT Screenshot" style="max-width: 100%; height: auto;">
</div>
※実際のものではありません

> [!WARNING]
>## 始める前に
> プログラミング弱者が作ったコードなのでエラーが発生する可能性があります。
> 環境によっては起動できない可能性があります。

## 環境構築

> [!WARNING]
> python3 がインストールされている前提です。

### クローン

GitHub からリポジトリをクローンします。

```bash
git clone https://github.com/nikkou-0814/Earth-Said-BOT.git
```

### 環境変数

1. .env をコピーします。

```bash
cp .env.example .env
```

Discord BOT のトークンとチャンネルIDを記載します。

2. TOKEN=<DISOCRD_TOKEN>

3. ChannelID=<DISCORD_ChannelID>

## 依存関係のインストールと起動

```bash
pip install -r requirements.txt

python bot.py
```