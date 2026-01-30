import { useState, useEffect, useMemo } from "react";
import Filters from "./components/Filters";
import CardList from "./components/CardList";
import TableView from "./components/TableView";
import Pagination from "./components/Pagination";

const API_BASE = import.meta.env.VITE_API_URL || "";

function App() {
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("analysis");

  const [filters, setFilters] = useState({
    keyword: "",
    inStockOnly: false,
    profitOnly: false,
  });

  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/cards`)
      .then((res) => {
        if (!res.ok) throw new Error(res.statusText || "APIエラー");
        return res.json();
      })
      .then((data) => {
        if (!Array.isArray(data)) throw new Error("データ形式が不正です");
        setCards(data);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const filteredData = useMemo(() => {
    return cards
      .filter((card) => {
        if (filters.keyword.trim()) {
          const kw = filters.keyword.toLowerCase().trim();
          const text = `${card.card_name} ${card.card_number} ${card.no}`.toLowerCase();
          if (!text.includes(kw)) return false;
        }
        if (filters.inStockOnly && !card.stock_normalized.includes("在庫あり"))
          return false;
        if (filters.profitOnly && card.profit <= 0) return false;
        return true;
      })
      .sort((a, b) => b.profit - a.profit);
  }, [cards, filters]);

  const stats = useMemo(
    () => ({
      total: cards.length,
      filtered: filteredData.length,
      profitable: filteredData.filter((c) => c.profit > 0).length,
      inStock: filteredData.filter((c) =>
        c.stock_normalized.includes("在庫あり")
      ).length,
    }),
    [cards.length, filteredData]
  );

  useEffect(() => {
    setCurrentPage(1);
  }, [filters]);

  const totalPages = Math.max(1, Math.ceil(filteredData.length / itemsPerPage));

  useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(totalPages);
  }, [totalPages, currentPage]);

  const currentData = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredData.slice(start, start + itemsPerPage);
  }, [filteredData, currentPage]);

  if (loading) {
    return (
      <div className="min-h-screen bg-bg-main flex items-center justify-center text-text-muted">
        読み込み中...
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-bg-main flex items-center justify-center p-6">
        <div className="bg-bg-card border border-profit-down rounded-lg p-6 max-w-md text-center">
          <p className="text-profit-down font-medium mb-2">データの取得に失敗しました</p>
          <p className="text-sm text-text-muted">{error}</p>
          <p className="text-xs text-text-muted mt-2">
            API（{API_BASE || "同オリジン"}/api/cards）が起動しているか確認してください。
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg-main flex flex-col md:flex-row font-sans text-text-main">
      {/* モバイル: フィルター折りたたみ */}
      <div className="md:hidden p-4 bg-bg-sidebar border-b border-border-custom">
        <details className="group">
          <summary className="font-bold cursor-pointer list-none flex items-center gap-2">
            <span className="group-open:rotate-90 transition-transform">▶</span>
            🔍 フィルター・統計
          </summary>
          <div className="mt-3 -mx-2">
            <Filters
              filters={filters}
              setFilters={setFilters}
              stats={stats}
            />
          </div>
        </details>
      </div>

      {/* デスクトップ: サイドバー */}
      <aside className="hidden md:block w-80 shrink-0 sticky top-0 h-screen overflow-y-auto">
        <Filters filters={filters} setFilters={setFilters} stats={stats} />
      </aside>

      <main className="flex-1 p-4 md:p-6 overflow-x-hidden">
        <div className="bg-gradient-to-br from-bg-card to-accent-light border border-border-custom rounded-xl p-6 mb-6 shadow-sm">
          <h1 className="text-xl md:text-2xl font-bold text-accent mb-1">
            🃏 ポケモンカード PSA10 買取比較
          </h1>
          <p className="text-text-muted text-sm">
            おたちゅう（買取）vs カードラッシュ（販売）の価格比較
          </p>
        </div>

        <div className="mb-4 border-b border-border-custom flex gap-4">
          <button
            type="button"
            className={`px-4 py-2 border-b-2 font-medium transition-colors ${
              activeTab === "analysis"
                ? "border-accent text-accent"
                : "border-transparent text-text-muted hover:text-text-main"
            }`}
            onClick={() => setActiveTab("analysis")}
          >
            📊 データ分析（PC）
          </button>
          <button
            type="button"
            className={`px-4 py-2 border-b-2 font-medium transition-colors ${
              activeTab === "research"
                ? "border-accent text-accent"
                : "border-transparent text-text-muted hover:text-text-main"
            }`}
            onClick={() => setActiveTab("research")}
          >
            📱 現場リサーチ（スマホ）
          </button>
        </div>

        <div className="space-y-6">
          {activeTab === "analysis" && (
            <>
              <section className="bg-bg-card border border-border-custom rounded-lg p-4 shadow-sm">
                <h3 className="font-bold text-text-main border-b-2 border-accent-light pb-2 mb-3">
                  📊 データ分析モード
                </h3>
                <p className="text-text-muted text-sm mb-4">
                  PCで見やすいテーブル形式。各列クリックでソート可能。
                </p>
                <TableView data={filteredData} />
              </section>

              <section className="bg-bg-card border border-border-custom rounded-lg p-4 shadow-sm">
                <h3 className="font-bold text-text-main border-b-2 border-accent-light pb-2 mb-3">
                  📱 カード一覧（現場リサーチと同じ表示）
                </h3>
              </section>
            </>
          )}

          {activeTab === "research" && (
            <section className="bg-bg-card border border-border-custom rounded-lg p-4 shadow-sm">
              <h3 className="font-bold text-text-main border-b-2 border-accent-light pb-2 mb-3">
                📱 現場リサーチモード
              </h3>
              <p className="text-text-muted text-sm mb-4">
                スマホで見やすいカード型リストです。
              </p>
            </section>
          )}

          {/* カード一覧 + ページネーション（両タブ共通） */}
          <div>
            <Pagination
              totalItems={filteredData.length}
              itemsPerPage={itemsPerPage}
              currentPage={currentPage}
              onPageChange={setCurrentPage}
            />
            <CardList data={currentData} />
            <Pagination
              totalItems={filteredData.length}
              itemsPerPage={itemsPerPage}
              currentPage={currentPage}
              onPageChange={setCurrentPage}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
