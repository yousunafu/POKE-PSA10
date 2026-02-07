/**
 * PSA9 ヤフオク相場 API
 * FastAPI から POST でカードリストを受け取り、ヤフオク落札統計・メルカリリンクを JSON で返す。
 *
 * デプロイ: 公開 → ウェブアプリ → 実行ユーザー:自分 / アクセス:全員
 */

/**
 * ヤフオク落札済み検索で平均・中央値・直近3件のリンクを取得
 * @param {string} cardName - カード名
 * @param {string} cardNum - 型番
 * @param {string} rarity - レア
 * @returns {Object} { yahooAvg, yahooMedian, recent1, recent2, recent3, mercariUrl, hasHistory }
 */
function getYahooStats(cardName, cardNum, rarity) {
  const searchQuery = `${cardName || ''} ${cardNum || ''} ${rarity || ''} PSA9`.trim();
  if (!searchQuery || searchQuery === 'PSA9') {
    return { yahooAvg: null, yahooMedian: null, recent1: null, recent2: null, recent3: null, mercariUrl: null, hasHistory: false };
  }

  const encodedQuery = encodeURIComponent(searchQuery);
  const yahooUrl = `https://auctions.yahoo.co.jp/closedsearch/closedsearch?p=${encodedQuery}`;

  try {
    const response = UrlFetchApp.fetch(yahooUrl, {
      muteHttpExceptions: true,
      headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36" }
    }).getContentText();

    const priceMatches = response.match(/class="Product__priceValue">([\d,]+)円/g);
    const urlMatches = response.match(/class="Product__titleLink" href="([^"]+)"/g);

    if (!priceMatches || priceMatches.length === 0) {
      const mercariUrl = `https://jp.mercari.com/search?keyword=${encodeURIComponent(searchQuery)}&status=sold_out&sort=created_time&order=desc`;
      return { yahooAvg: null, yahooMedian: null, recent1: null, recent2: null, recent3: null, mercariUrl: mercariUrl, hasHistory: false };
    }

    const prices = priceMatches.map(function(m) {
      return parseInt(m.match(/[\d,]+/)[0].replace(/,/g, ""), 10);
    });
    let links = [];
    if (urlMatches) {
      links = urlMatches.map(function(m) {
        var url = m.match(/href="([^"]+)"/)[1];
        return url.indexOf("http") === 0 ? url : "https://auctions.yahoo.co.jp" + url;
      });
    }

    const avg = Math.round(prices.reduce(function(a, b) { return a + b; }, 0) / prices.length);
    const sortedPrices = prices.slice().sort(function(a, b) { return a - b; });
    const mid = Math.floor(sortedPrices.length / 2);
    const median = sortedPrices.length % 2 !== 0
      ? sortedPrices[mid]
      : Math.round((sortedPrices[mid - 1] + sortedPrices[mid]) / 2);

    const recent1 = prices[0] && links[0] ? { price: prices[0], url: links[0] } : null;
    const recent2 = prices[1] && links[1] ? { price: prices[1], url: links[1] } : null;
    const recent3 = prices[2] && links[2] ? { price: prices[2], url: links[2] } : null;

    const mercariUrl = `https://jp.mercari.com/search?keyword=${encodeURIComponent(searchQuery)}&status=sold_out&sort=created_time&order=desc`;

    return {
      yahooAvg: avg,
      yahooMedian: median,
      recent1: recent1,
      recent2: recent2,
      recent3: recent3,
      mercariUrl: mercariUrl,
      hasHistory: true
    };
  } catch (e) {
    const mercariUrl = `https://jp.mercari.com/search?keyword=${encodeURIComponent(searchQuery)}&status=sold_out&sort=created_time&order=desc`;
    return { yahooAvg: null, yahooMedian: null, recent1: null, recent2: null, recent3: null, mercariUrl: mercariUrl, hasHistory: false, error: e.toString() };
  }
}

/**
 * POST リクエストを受け付けるエントリポイント
 * FastAPI から { "cards": [ { "id", "cardName", "cardNum", "rarity" } ] } の形式で送信
 */
function doPost(e) {
  try {
    const params = JSON.parse(e.postData.contents);
    const cards = params.cards || [];

    if (!Array.isArray(cards) || cards.length === 0) {
      return createJsonOutput({ error: "cards が空です", results: [] });
    }

    if (cards.length > 30) {
      return createJsonOutput({ error: "1回あたり30件までにしてください", results: [] });
    }

    const results = [];
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      var stats = getYahooStats(
        card.cardName || card.card_name,
        card.cardNum || card.card_number,
        card.rarity
      );
      results.push({
        id: card.id || card.cardNum || card.card_number || "",
        cardName: card.cardName || card.card_name || "",
        cardNum: card.cardNum || card.card_number || "",
        rarity: card.rarity || "",
        yahooAvg: stats.yahooAvg,
        yahooMedian: stats.yahooMedian,
        recent1: stats.recent1,
        recent2: stats.recent2,
        recent3: stats.recent3,
        mercariUrl: stats.mercariUrl,
        hasHistory: stats.hasHistory,
        error: stats.error || null
      });
      Utilities.sleep(600);
    }

    return createJsonOutput({ results: results });
  } catch (err) {
    return createJsonOutput({ error: err.toString(), results: [] });
  }
}

function createJsonOutput(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * GET 用（デプロイ確認・ヘルスチェック）
 * ブラウザでURLを開くと "PSA9 API is running" と表示される
 */
function doGet(e) {
  return ContentService.createTextOutput("PSA9 API is running. Use POST with { cards: [...] }.")
    .setMimeType(ContentService.MimeType.TEXT);
}
