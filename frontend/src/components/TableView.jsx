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

function getDisplayNetProfit(card, miscExpenses = 0) {
  if (!card.profitInfo) return 0;
  return card.profitInfo.netProfit - (Number(miscExpenses) || 0);
}

export default function TableView({ data, miscExpenses = 0 }) {
  const [sortKey, setSortKey] = useState("profit");
  const [sortAsc, setSortAsc] = useState(true); // true = 降順（利益高い順がデフォルト）

  const sortedData = useMemo(() => {
    const arr = [...(data || [])];
    arr.sort((a, b) => {
      let va, vb;
      if (sortKey === "profit") {
        va = getDisplayNetProfit(a, miscExpenses);
        vb = getDisplayNetProfit(b, miscExpenses);
      } else if (sortKey === "profitRate") {
        va = a.profitInfo?.profitRate ?? 0;
        vb = b.profitInfo?.profitRate ?? 0;
      } else if (sortKey === "gradingFee") {
        va = a.profitInfo?.gradingFee ?? 0;
        vb = b.profitInfo?.gradingFee ?? 0;
      } else {
        va = a[sortKey];
        vb = b[sortKey];
      }
      if (typeof va === "string") va = (va || "").toLowerCase();
      if (typeof vb === "string") vb = (vb || "").toLowerCase();
      if (va < vb) return sortAsc ? 1 : -1;
      if (va > vb) return sortAsc ? -1 : 1;
      return 0;
    });
    return arr;
  }, [data, sortKey, sortAsc, miscExpenses]);

  const toggleSort = (key) => {
    if (sortKey === key) setSortAsc((s) => !s);
    else {
      setSortKey(key);
      setSortAsc(key === "profit" || key === "profitRate");
    }
  };

  const Th = ({ label, colKey, className = "" }) => (
    <th
      className={`border border-border-custom px-3 py-2 text-left text-sm font-medium text-text-main bg-bg-sidebar cursor-pointer hover:bg-accent-light/50 select-none ${className}`}
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

  const displayProfits = sortedData.map((c) => getDisplayNetProfit(c, miscExpenses));
  const avgProfit = displayProfits.length
    ? displayProfits.reduce((acc, p) => acc + p, 0) / displayProfits.length
    : 0;
  const maxProfit = displayProfits.length ? Math.max(...displayProfits) : 0;
  const minProfit = displayProfits.length ? Math.min(...displayProfits) : 0;

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-lg border border-border-custom shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <Th label="画像" colKey="card_name" />
              <Th label="カード名" colKey="card_name" />
              <Th label="型番" colKey="card_number" />
              <Th label="相場" colKey="pokeca_chart_url" className="whitespace-nowrap min-w-[5rem]" />
              <Th label="PSA10" colKey="buy_price" />
              <Th label="仕入" colKey="sell_price" />
              <Th label="鑑定" colKey="gradingFee" className="whitespace-nowrap" />
              <Th label="手取" colKey="profit" />
              <Th label="利益率" colKey="profitRate" />
              <Th label="在庫" colKey="stock_normalized" />
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
                <td className="border border-border-custom px-3 py-2 whitespace-nowrap">
                  {card.pokeca_chart_url ? (
                    <a
                      href={card.pokeca_chart_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent hover:underline text-xs whitespace-nowrap"
                    >
                      📊 相場
                    </a>
                  ) : (
                    <span className="text-text-muted text-xs">—</span>
                  )}
                </td>
                <td className="border border-border-custom px-3 py-2">
                  {card.profitInfo.psa10Price.toLocaleString()}円
                </td>
                <td className="border border-border-custom px-3 py-2">
                  {card.profitInfo.purchasePrice.toLocaleString()}円
                </td>
                <td className="border border-border-custom px-3 py-2 text-text-muted">
                  {card.profitInfo.gradingFee.toLocaleString()}円
                </td>
                <td className="border border-border-custom px-3 py-2">
                  {formatProfitCell(getDisplayNetProfit(card, miscExpenses))}
                </td>
                <td className="border border-border-custom px-3 py-2">
                  <span
                    className={
                      card.profitInfo.profitRate >= 20
                        ? "text-profit-up font-medium"
                        : card.profitInfo.profitRate >= 15
                          ? "text-yellow-600 font-medium"
                          : ""
                    }
                  >
                    {card.profitInfo.profitRate.toFixed(1)}%
                  </span>
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
        💡 手取り利益の 平均: {Math.floor(avgProfit).toLocaleString()}円 |
        最大: {maxProfit.toLocaleString()}円 | 最小: {minProfit.toLocaleString()}円
      </div>
    </div>
  );
}
