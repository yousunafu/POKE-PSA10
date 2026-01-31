export default function Filters({ filters, setFilters, stats }) {
  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    let next = value;
    if (type === "checkbox") next = checked;
    else if (type === "number") next = value === "" ? null : Number(value);
    if (name === "miscExpenses" && (next === null || next === undefined))
      next = 0;
    setFilters((prev) => ({ ...prev, [name]: next }));
  };

  return (
    <div className="bg-bg-sidebar border-r border-border-custom p-4 h-full">
      <div className="bg-bg-card border border-border-custom rounded-lg p-4 mb-4 shadow-sm">
        <h3 className="font-bold text-text-main border-b-2 border-accent-light pb-2 mb-3">
          🔍 フィルター
        </h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-main mb-1">
              キーワード検索
            </label>
            <input
              type="text"
              name="keyword"
              value={filters.keyword}
              onChange={handleChange}
              placeholder="カード名・型番"
              className="w-full border border-border-custom rounded px-3 py-2 text-sm focus:outline-none focus:border-accent"
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="flex items-center gap-2 text-sm text-text-main cursor-pointer">
              <input
                type="checkbox"
                name="inStockOnly"
                checked={filters.inStockOnly}
                onChange={handleChange}
                className="rounded text-accent focus:ring-accent"
              />
              在庫ありのみ表示
            </label>
            <label className="flex items-center gap-2 text-sm text-text-main cursor-pointer">
              <input
                type="checkbox"
                name="profitOnly"
                checked={filters.profitOnly}
                onChange={handleChange}
                className="rounded text-accent focus:ring-accent"
              />
              利益が出る商品のみ表示（諸費用控除後）
            </label>
          </div>
        </div>
      </div>

      <div className="bg-bg-card border border-border-custom rounded-lg p-4 mb-4 shadow-sm">
        <h3 className="font-bold text-text-main border-b-2 border-accent-light pb-2 mb-3">
          💰 価格・諸費用
        </h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-main mb-1">
              販売価格 最小（円）
            </label>
            <input
              type="number"
              name="priceMin"
              min={0}
              step={1000}
              value={filters.priceMin ?? ""}
              onChange={handleChange}
              placeholder="0で制限なし"
              className="w-full border border-border-custom rounded px-3 py-2 text-sm focus:outline-none focus:border-accent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-main mb-1">
              販売価格 最大（円）
            </label>
            <input
              type="number"
              name="priceMax"
              min={0}
              step={1000}
              value={filters.priceMax ?? ""}
              onChange={handleChange}
              placeholder="空で制限なし"
              className="w-full border border-border-custom rounded px-3 py-2 text-sm focus:outline-none focus:border-accent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-main mb-1">
              諸費用（円）
            </label>
            <input
              type="number"
              name="miscExpenses"
              min={0}
              step={500}
              value={filters.miscExpenses ?? 0}
              onChange={handleChange}
              placeholder="鑑定費用など"
              className="w-full border border-border-custom rounded px-3 py-2 text-sm focus:outline-none focus:border-accent"
            />
            <p className="text-xs text-text-muted mt-1">予想利益から自動で控除します</p>
          </div>
        </div>
      </div>

      <div className="bg-bg-card border border-border-custom rounded-lg p-4 shadow-sm">
        <h3 className="font-bold text-text-main border-b-2 border-accent-light pb-2 mb-3">
          📊 統計
        </h3>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-text-muted">全データ:</span>
            <span className="font-bold">{stats.total.toLocaleString()}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">表示中:</span>
            <span className="font-bold">{stats.filtered.toLocaleString()}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">利益あり:</span>
            <span className="font-bold text-profit-up">
              {stats.profitable.toLocaleString()}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">在庫あり:</span>
            <span className="font-bold">{stats.inStock.toLocaleString()}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
