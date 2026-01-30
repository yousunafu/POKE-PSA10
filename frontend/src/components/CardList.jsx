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

export default function CardList({ data }) {
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
              <span className="text-text-muted mr-1">予想最大利益:</span>
              {formatProfit(card.profit)}
            </div>
            <div className="text-sm space-y-1">
              <div>
                <span className="text-text-muted">買取価格（おたちゅう PSA10）:</span>{" "}
                {Number(card.buy_price).toLocaleString()}円
              </div>
              <div>
                <span className="text-text-muted">販売価格（ラッシュ 素体A）:</span>{" "}
                {card.sell_price != null && card.sell_price !== ""
                  ? `${Number(card.sell_price).toLocaleString()}円`
                  : "取得失敗"}
              </div>
              <div>
                <span className="text-text-muted">在庫:</span>{" "}
                {card.stock_normalized}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
