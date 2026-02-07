/**
 * PSA9 ヤフオク相場 API
 * Code.gs にこの内容をそのまま貼り付けてください
 */

function doGet(e) {
  return ContentService.createTextOutput("PSA9 API is running. Use POST with { cards: [...] }.")
    .setMimeType(ContentService.MimeType.TEXT);
}

function doPost(e) {
  try {
    var params = JSON.parse(e.postData.contents);
    var cards = params.cards || [];

    if (!Array.isArray(cards) || cards.length === 0) {
      return createJsonOutput({ error: "cards が空です", results: [] });
    }

    if (cards.length > 30) {
      return createJsonOutput({ error: "1回あたり30件までにしてください", results: [] });
    }

    var results = [];
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      var stats = getYahooStats(
        card.cardName || card.card_name || "",
        card.cardNum || card.card_number || "",
        card.rarity || ""
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

function getYahooStats(cardName, cardNum, rarity) {
  var searchQuery = (cardName + " " + cardNum + " " + rarity + " PSA9").trim();
  if (!searchQuery || searchQuery === "PSA9") {
    return { yahooAvg: null, yahooMedian: null, recent1: null, recent2: null, recent3: null, mercariUrl: null, hasHistory: false };
  }

  var encodedQuery = encodeURIComponent(searchQuery);
  var yahooUrl = "https://auctions.yahoo.co.jp/closedsearch/closedsearch?p=" + encodedQuery;

  try {
    var response = UrlFetchApp.fetch(yahooUrl, {
      muteHttpExceptions: true,
      headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" }
    }).getContentText();

    var priceMatches = response.match(/class="Product__priceValue">([\d,]+)円/g);
    var urlMatches = response.match(/class="Product__titleLink" href="([^"]+)"/g);

    if (!priceMatches || priceMatches.length === 0) {
      var mercariUrl = "https://jp.mercari.com/search?keyword=" + encodeURIComponent(searchQuery) + "&status=sold_out&sort=created_time&order=desc";
      return { yahooAvg: null, yahooMedian: null, recent1: null, recent2: null, recent3: null, mercariUrl: mercariUrl, hasHistory: false };
    }

    var prices = [];
    for (var p = 0; p < priceMatches.length; p++) {
      prices.push(parseInt(priceMatches[p].match(/[\d,]+/)[0].replace(/,/g, ""), 10));
    }
    var links = [];
    if (urlMatches) {
      for (var u = 0; u < urlMatches.length; u++) {
        var url = urlMatches[u].match(/href="([^"]+)"/)[1];
        links.push(url.indexOf("http") === 0 ? url : "https://auctions.yahoo.co.jp" + url);
      }
    }

    var sum = 0;
    for (var s = 0; s < prices.length; s++) {
      sum += prices[s];
    }
    var avg = Math.round(sum / prices.length);
    var sortedPrices = prices.slice().sort(function(a, b) { return a - b; });
    var mid = Math.floor(sortedPrices.length / 2);
    var median = sortedPrices.length % 2 !== 0
      ? sortedPrices[mid]
      : Math.round((sortedPrices[mid - 1] + sortedPrices[mid]) / 2);

    var recent1 = (prices[0] && links[0]) ? { price: prices[0], url: links[0] } : null;
    var recent2 = (prices[1] && links[1]) ? { price: prices[1], url: links[1] } : null;
    var recent3 = (prices[2] && links[2]) ? { price: prices[2], url: links[2] } : null;
    var mercariUrl = "https://jp.mercari.com/search?keyword=" + encodeURIComponent(searchQuery) + "&status=sold_out&sort=created_time&order=desc";

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
    var mercariUrl = "https://jp.mercari.com/search?keyword=" + encodeURIComponent(searchQuery) + "&status=sold_out&sort=created_time&order=desc";
    return { yahooAvg: null, yahooMedian: null, recent1: null, recent2: null, recent3: null, mercariUrl: mercariUrl, hasHistory: false, error: e.toString() };
  }
}
