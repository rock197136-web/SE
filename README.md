# 陀螺行情：正常查詢與 GitHub 定時接通版

主畫面改為依陀螺型號／名稱分類的「社團買賣貼文」，可搜尋並按 BX／UX／CX／BXG、出售／已售出標記／收購／競標篩選。成交統計另外切換。價格節錄附原貼文連結，不將整批價或開價偽裝成單顆成交價。

## 先做這五步就能接通公開貼文更新

1. **下載 ZIP 並解壓縮。** GitHub 不會自動解壓 ZIP，所以不能只把 ZIP 上傳到 repo。
2. **把 github-live-market 資料夾裡面的全部檔案上傳到 repo 根目錄。** index.html、snapshot.json、data、scripts、tests、.github 應直接在根目錄；不要多包一層資料夾。特別確認 `.github/workflows/update-and-deploy.yml` 存在。
3. **Settings → Pages → Source 選 GitHub Actions。**
4. **Settings → Actions → General → Workflow permissions 選 Read and write permissions → Save。**
5. **Actions → Update market and deploy Pages → Run workflow。** 執行成功後，開啟 Settings → Pages 顯示的網址。

**不必先取得 API key：這個版本會嘗試 Firecrawl 免 key 低量搜尋，每個社團每次最多 3 筆搜尋結果。** 已實測公開搜尋可回傳貼文；免 key 模式可能受頻率、額度或服務限制。需要較多結果時，再到 Firecrawl 取得自己的 API key，填到 repo 的 Settings → Secrets and variables → Actions → New repository secret，Name 為 FIRECRAWL_API_KEY，Secret 為該 key。啟用 key 後每個社團每次最多 20 筆。

四個指定社團：797104363091043、411150865948422、1492428162434388、1240639167707723。

## 怎樣確認真的接通

- Actions 的執行紀錄中，Collect public references and dated market feed 的輸出應出現 `search_ok: 4`（四個社團搜尋成功）。
- 網站「線上資料狀態」應顯示服務上次檢查時間。
- 瀏覽器開啟網站同一個目錄下的 `snapshot.json`，應顯示 JSON，內有 references 與 collection；若仍是 404，代表部署少了資料檔或網站目錄不正確。
- 第一次執行即可發布；之後每小時第 17 分鐘更新。GitHub 排程可能延遲；公開 repo 長期無活動時需重新啟用。
- 頁面開啟立即同步，停留期間每五分鐘檢查；同步失敗保留已收錄資訊，不會整頁空白。

## 這次修正的 404

原版本只有 HTML 時，`snapshot.json` 不存在，會回傳 404。本版 ZIP 根目錄補上 snapshot.json，Actions 同時更新 root 與 data/snapshot.json，Pages 產物也包含 snapshot.json。

HTML 讀取時會先找同目錄 snapshot.json，再找 data/snapshot.json。只開 HTML 或部署漏檔時，仍可先查看隨網站發佈的公開貼文，並明確提示尚未線上同步。**這個備用內容不是定時蒐集的替代品；依上述五步啟用 Actions 才會更新。**

## 日期與價格的規則

近 7／14／30 天只依文章真正發文日期 published_at 判斷。搜尋節錄通常沒有可核對的確切發文日期，因此另列「已收錄買賣資訊／發文日期待核對」，不能把今天搜尋到的舊文當成今天發文。

主畫面即使只有節錄，也能依型號／名稱分類並查看原文。未明確指出的品項归入綜合／配件；多品項貼文可能出現在不同分類，不把整批金額拆成單顆價。

**公開搜尋接通不代表 Facebook 原文或真正成交價格已完整取得。** 目前原文讀取服務回覆不支援 Facebook；因此完整發文日期、成交佐證仍需另一個授權的原文資料來源。要接這個來源，可設定 MARKET_FEED_URLS，格式見下面進階說明。

---

## Feed 欄位

最外層 JSON 為 `{"posts": [...]}`。每篇原文包括：

| 欄位 | 內容 |
| --- | --- |
| post_url | 四個指定社團 `/groups/社團ID/posts/原文ID/` 的 HTTPS 原貼文網址 |
| group_name | 社團名稱 |
| published_at | 真實原文發文時間，ISO8601 含秒與時區 |
| capture_method | `original_post` |
| excerpt | 實際原文節錄 |
| transaction_evidence | 可選的其他佐證文字 |
| listings | 該貼文的完整商品列表；同一原文的新版本會替換先前列表 |

每件商品包括 `model`（data/models.json 中的完整型號）、`price_twd`（新台幣整數）、`status`（成交／在售／收購／競標）、`kind`（整顆／零件／組合／拆賣／頂重）、`condition`（沒寫／全新／拆檢／二手）、`version`（留空或日版／台版／亞版／美版／韓版／港版／泰版）。

**成交價格必須有 price_basis 與 evidence_excerpt；sold_at 選填。欄位說明如下，否則整個來源批次會被拒收，保留先前資料：**

- `sold_at`：選填的實際成交時間，ISO8601 含秒與時區。若提供，不得早於發文或晚於目前時間；不參與近期篩選。
- `price_basis`：固定為 `seller_confirmed_final`。
- `evidence_excerpt`：賣家確認最終成交價的原文節錄；僅有「已售出」及原開價，不符合這個要求。

零件單賣再填 `part_category`、`part_id`、`part_name`。整批合售不拆成單顆價；不同版本、零件、頂重保留分類。

來源提供的聲明仍需信任與核驗；程式只能檢查格式、一致性與日期，不會神奇證明交易真實。

## 驗證與操作

- `python -m unittest discover -s tests -v`：執行成交欄位、防重、失敗保留測試。
- `python scripts/update_market.py`：在有相同環境變數的環境更新 data/snapshot.json。
- Actions 執行紀錄會显示來源成功數與狀態。拒收資料的來源不會把舊紀錄清空。
- 搜尋結果一律視為未分類參考，沒有精確文章發文日期，不能進成交統計；內容可能含舊文或相鄰貼文，需開原文核對。
- `.github`、scripts、tests 不會作為 Pages 公開網站檔案；Pages 部署只包含 index.html、snapshot.json。

參考官方文件：
- https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- https://docs.firecrawl.dev/api-reference/endpoint/search
