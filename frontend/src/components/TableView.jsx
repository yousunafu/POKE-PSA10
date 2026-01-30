import { useState, useMemo } from "react";

function formatProfitCell(profit) {
  if (profit > 0)
    return (
      <span className="text-profit-up font-medium">
        🟢 +{profit.toLocaleString()}円
      </span>
    );
  if (profit < 0)
    return (
      <span className="text-profit-down font-medium">
        🔴 {profit.toLocaleString()}円
      </span>
    );
  return <span>{profit.toLocaleString()}円</span>;
}

export default function TableView({ data }) {
  const [sortKey, setSortKey] = useState("profit");
  const [sortAsc, setSortAsc] = useState(false);

  const sortedData = useMemo(() => {
    const arr = [...(data || [])];
    arr.sort((a, b) => {
      let va = a[sortKey];
      let vb = b[sortKey];
      if (typeof va === "string") va = (va || "").toLowerCase();
      if (typeof vb === "string") vb = (vb || "").toLowerCase();
      if (va < vb) return sortAsc ? 1 : -1;
      if (va > vb) return sortAsc ? -1 : 1;
      return 0;
    });
    return arr;
  }, [data, sortKey, sortAsc]);

  const toggleSort = (key) => {
    if (sortKey === key) setSortAsc((s) => !s);
    else {
      setSortKey(key);
      setSortAsc(key === "profit" ? false : true);
    }
  };

  const Th = ({ label, colKey }) => (
    <th
      className="border border-border-custom px-3 py-2 text-left text-sm font-medium text-text-main bg-bg-sidebar cursor-pointer hover:bg-accent-light/50 select-none"
      onClick={() => toggleSort(colKey)}
    >
      {label} {sortKey === colKey && (sortAsc ? "↑" : "↓")}
    </th>
  );

  if (!data || data.length === 0) {
    return (
      <div className="bg-bg-card border border-border-custom rounded-lg p-6 text-center text-text-muted">
        表示するデータがありません。
      </div>
    );
  }

  const avgProfit =
    sortedData.reduce((acc, c) => acc + c.profit, 0) / sortedData.length;
  const maxProfit = Math.max(...sortedData.map((c) => c.profit));
  const minProfit = Math.min(...sortedData.map((c) => c.profit));

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-lg border border-border-custom shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <Th label="画像" colKey="card_name" />
              <Th label="カード名" colKey="card_name" />
              <Th label="型番" colKey="card_number" />
              <Th label="買取価格（おたちゅう）" colKey="buy_price" />
              <Th label="販売価格（ラッシュ）" colKey="sell_price" />
              <Th label="予想最大利益" colKey="profit" />
              <Th label="在庫状況" colKey="stock_normalized" />
            </tr>
          </thead>
          <tbody>
            {sortedData.map((card) => (
              <tr key={card.id} className="bg-bg-card hover:bg-gray-50/50">
                <td className="border border-border-custom px-2 py-1 align-middle">
                  {card.image_url ? (
                    <img
                      src={card.image_url}
                      alt=""
                      className="h-12 w-auto object-contain"
                      onError={(e) => {
                        e.target.style.display = "none";
                      }}
                    />
                  ) : (
                    <span className="text-text-muted text-xs">—</span>
                  )}
                </td>
                <td className="border border-border-custom px-3 py-2 text-text-main">
                  {card.card_name}
                </td>
                <td className="border border-border-custom px-3 py-2 text-text-muted">
                  {card.card_number || "—"}
                </td>
                <td className="border border-border-custom px-3 py-2">
                  {Number(card.buy_price).toLocaleString()}円
                </td>
                <td className="border border-border-custom px-3 py-2">
                  {card.sell_price != null && card.sell_price !== ""
                    ? `${Number(card.sell_price).toLocaleString()}円`
                    : "—"}
                </td>
                <td className="border border-border-custom px-3 py-2">
                  {formatProfitCell(card.profit)}
                </td>
                <td className="border border-border-custom px-3 py-2 text-text-muted">
                  {card.stock_normalized}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="bg-bg-card border border-border-custom rounded-lg px-4 py-3 text-sm text-text-main">
        💡 予想最大利益の 平均: {Math.floor(avgProfit).toLocaleString()}円 |
        最大: {maxProfit.toLocaleString()}円 | 最小: {minProfit.toLocaleString()}円
      </div>
    </div>
  );
}
