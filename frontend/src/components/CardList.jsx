import { useState } from "react";

function formatProfit(profit) {
  if (profit > 0)
    return (
      <span className="font-bold text-lg text-profit-up">+{profit.toLocaleString()}円</span>
    );
  if (profit < 0)
    return (
      <span className="font-bold text-lg text-profit-down">
        {profit.toLocaleString()}円
      </span>
    );
  return <span className="text-text-main">{profit.toLocaleString()}円</span>;
}

function getDisplayNetProfit(card, miscExpenses = 0) {
  if (!card.profitInfo) return 0;
  return card.profitInfo.netProfit - (Number(miscExpenses) || 0);
}

export default function CardList({ data, miscExpenses = 0, psa9Stats = {}, showPsa9Stats = false, showGradingFee = false }) {
  const [failedImages, setFailedImages] = useState(new Set());

  if (!data || data.length === 0) {
    return (
      <div className="bg-bg-card border border-border-custom rounded-lg p-6 text-center text-text-muted">
        表示するデータがありません。
      </div>
    );
  }

  const showImage = (card) =>
    card.image_url &&
    card.image_url !== "取得失敗" &&
    !failedImages.has(card.id);

  return (
    <div className="space-y-4">
      {data.map((card) => (
        <div
          key={card.id}
          className="bg-bg-card border border-border-custom rounded-lg p-4 shadow-sm flex flex-col md:flex-row gap-4"
        >
          <div className="md:w-1/3 shrink-0 flex justify-center items-start">
            {showImage(card) ? (
              <img
                src={card.image_url}
                alt={card.card_name}
                className="max-h-48 w-auto object-contain rounded"
                onError={() =>
                  setFailedImages((prev) => new Set(prev).add(card.id))
                }
              />
            ) : (
              <div className="text-text-muted text-sm py-8">
                {card.image_url && card.image_url !== "取得失敗"
                  ? "📷 画像読み込みエラー"
                  : "📷 画像なし"}
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-bold text-text-main text-lg mb-1">
              {card.card_name}
            </div>
            {card.card_number && (
              <div className="text-sm text-text-muted mb-2">
                型番: {card.card_number}
              </div>
            )}
            <div className="mb-2">
              <span className="text-text-muted mr-1">手取り利益:</span>
              {formatProfit(getDisplayNetProfit(card, miscExpenses))}
              {card.profitInfo?.riskReward != null && (
                <div className="text-xs text-profit-down mt-0.5">
                  リスク: {card.profitInfo.riskReward.toLocaleString()}円
                </div>
              )}
            </div>
            <div className="text-sm space-y-1">
              <div>
                <span className="text-text-muted">PSA10:</span>{" "}
                {card.profitInfo.psa10Price.toLocaleString()}円
              </div>
              <div>
                <span className="text-text-muted">仕入:</span>{" "}
                {card.profitInfo.purchasePrice.toLocaleString()}円
              </div>
              {showGradingFee && (
                <div>
                  <span className="text-text-muted">鑑定:</span>{" "}
                  {card.profitInfo.gradingFee.toLocaleString()}円
                  {card.profitInfo.isExpress ? "（快速1ヶ月）" : "（標準2〜3ヶ月）"}
                </div>
              )}
              <div>
                <span className="text-text-muted">利益率:</span>{" "}
                <span
                  className={
                    card.profitInfo.profitRate >= 20
                      ? "font-medium text-profit-up"
                      : card.profitInfo.profitRate >= 15
                        ? "font-medium text-yellow-600"
                        : ""
                  }
                >
                  {card.profitInfo.profitRate.toFixed(1)}%
                </span>
                {card.profitInfo.monthlyRate != null && (
                  <span className="text-text-muted ml-1">
                    （月換算: 約{card.profitInfo.monthlyRate.toFixed(1)}%）
                  </span>
                )}
              </div>
              <div>
                <span className="text-text-muted">在庫:</span>{" "}
                {card.stock_normalized}
              </div>
            </div>
            {card.pokeca_chart_url && (
              <a
                href={card.pokeca_chart_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 mt-2 px-3 py-1.5 text-sm font-medium rounded border border-accent text-accent hover:bg-accent-light/30 transition-colors"
              >
                📊 みんなのポケカ相場で相場を見る
              </a>
            )}
            {showPsa9Stats && psa9Stats[card.id] && (
              <div className="mt-2 space-y-1 text-sm">
                {psa9Stats[card.id].yahooAvg != null && (
                  <div>
                    <span className="text-text-muted">ヤフオク平均:</span>{" "}
                    <span className="font-medium">{psa9Stats[card.id].yahooAvg.toLocaleString()}円</span>
                  </div>
                )}
                {[psa9Stats[card.id].recent1, psa9Stats[card.id].recent2, psa9Stats[card.id].recent3]
                  .filter(Boolean)
                  .map((r, i) => (
                    <a
                      key={i}
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block text-accent hover:underline"
                    >
                      直近{i + 1}: {r.price.toLocaleString()}円
                    </a>
                  ))}
                {psa9Stats[card.id].mercariUrl && (
                  <a
                    href={psa9Stats[card.id].mercariUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded border border-accent text-accent hover:bg-accent-light/30 transition-colors"
                  >
                    📦 メルカリで売れ筋を確認
                  </a>
                )}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
