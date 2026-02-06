import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import Filters from "./components/Filters";
import CardList from "./components/CardList";
import TableView from "./components/TableView";
import Pagination from "./components/Pagination";
import { calcCardProfit } from "./utils/profitCalc";

const API_BASE = import.meta.env.VITE_API_URL || "";
const MOBILE_BREAKPOINT = 768;
const MOBILE_INITIAL_ITEMS = 20;
const MOBILE_LOAD_MORE = 20;

const INITIAL_FILTERS = {
  keyword: "",
  inStockOnly: false,
  profitRateMin: 20,
  priceMin: null,
  priceMax: null,
  miscExpenses: 0,
};

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== "undefined" && window.innerWidth < MOBILE_BREAKPOINT
  );
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
    const handler = (e) => setIsMobile(e.matches);
    handler(mq);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return isMobile;
}

function App() {
  const isMobile = useIsMobile();
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState(() =>
    typeof window !== "undefined" && window.innerWidth < MOBILE_BREAKPOINT
      ? "research"
      : "analysis"
  );
  const [bottomMenuOpen, setBottomMenuOpen] = useState(false);
  const [mobileVisibleCount, setMobileVisibleCount] = useState(MOBILE_INITIAL_ITEMS);
  const loadMoreSentinelRef = useRef(null);

  const [filters, setFilters] = useState(INITIAL_FILTERS);

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

  const miscExpenses = Number(filters.miscExpenses) || 0;
  const profitRateMin = filters.profitRateMin != null && filters.profitRateMin !== ""
    ? Number(filters.profitRateMin)
    : 0;

  const filteredData = useMemo(() => {
    return cards
      .map((card) => {
        const info = calcCardProfit(card);
        return { ...card, profitInfo: info };
      })
      .filter((card) => {
        if (card.profitInfo == null) return false;
        if (filters.keyword.trim()) {
          const kw = filters.keyword.toLowerCase().trim();
          const text = `${card.card_name} ${card.card_number} ${card.no}`.toLowerCase();
          if (!text.includes(kw)) return false;
        }
        const sell = Number(card.sell_price) || 0;
        if (filters.priceMin != null && filters.priceMin !== "" && sell < Number(filters.priceMin))
          return false;
        if (filters.priceMax != null && filters.priceMax !== "" && sell > Number(filters.priceMax))
          return false;
        if (filters.inStockOnly && !card.stock_normalized.includes("在庫あり"))
          return false;
        if (card.profitInfo.profitRate < profitRateMin) return false;
        return true;
      })
      .sort((a, b) => (b.profitInfo.netProfit - miscExpenses) - (a.profitInfo.netProfit - miscExpenses));
  }, [cards, filters, miscExpenses, profitRateMin]);

  const getDisplayNetProfit = (card) =>
    card.profitInfo ? card.profitInfo.netProfit - miscExpenses : 0;

  const stats = useMemo(
    () => ({
      total: cards.length,
      filtered: filteredData.length,
      hiddenByProfit: cards.filter((c) => calcCardProfit(c) == null).length,
      profitable: filteredData.filter((c) => getDisplayNetProfit(c) > 0).length,
      inStock: filteredData.filter((c) =>
        c.stock_normalized.includes("在庫あり")
      ).length,
    }),
    [cards, filteredData, miscExpenses]
  );

  useEffect(() => {
    setCurrentPage(1);
    setMobileVisibleCount(MOBILE_INITIAL_ITEMS);
  }, [filters]);

  const totalPages = Math.max(1, Math.ceil(filteredData.length / itemsPerPage));

  useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(totalPages);
  }, [totalPages, currentPage]);

  const currentData = useMemo(() => {
    if (isMobile) {
      return filteredData.slice(0, mobileVisibleCount);
    }
    const start = (currentPage - 1) * itemsPerPage;
    return filteredData.slice(start, start + itemsPerPage);
  }, [filteredData, currentPage, isMobile, mobileVisibleCount]);

  const hasMoreMobile = mobileVisibleCount < filteredData.length;
  const loadMore = useCallback(() => {
    setMobileVisibleCount((prev) =>
      Math.min(prev + MOBILE_LOAD_MORE, filteredData.length)
    );
  }, [filteredData.length]);

  useEffect(() => {
    if (!isMobile || !hasMoreMobile) return;
    const el = loadMoreSentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) loadMore();
      },
      { rootMargin: "100px", threshold: 0 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [isMobile, hasMoreMobile, loadMore]);

  const resetToInitial = useCallback(() => {
    setFilters(INITIAL_FILTERS);
    setCurrentPage(1);
    setMobileVisibleCount(MOBILE_INITIAL_ITEMS);
    setActiveTab(
      typeof window !== "undefined" && window.innerWidth < MOBILE_BREAKPOINT
        ? "research"
        : "analysis"
    );
    setBottomMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

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
    <div className="min-h-screen bg-bg-main flex flex-col md:flex-row font-sans text-text-main pb-16 md:pb-0">
      {/* デスクトップ: サイドバー */}
      <aside className="hidden md:block w-80 shrink-0 sticky top-0 h-screen overflow-y-auto">
        <Filters filters={filters} setFilters={setFilters} stats={stats} />
      </aside>

      <main className="flex-1 p-4 md:p-6 overflow-x-hidden">
        <button
          type="button"
          onClick={resetToInitial}
          className="w-full text-left bg-gradient-to-br from-bg-card to-accent-light border border-border-custom rounded-xl p-6 mb-6 shadow-sm hover:from-accent-light/30 hover:to-accent-light/50 transition-colors cursor-pointer"
          aria-label="クリックで初期状態に戻る"
        >
          <h1 className="text-xl md:text-2xl font-bold text-accent mb-1">
            🃏 ポケモンカード PSA10 買取比較
          </h1>
          <p className="text-text-muted text-sm">
            おたちゅう（買取）vs カードラッシュ（販売）の価格比較
          </p>
          <p className="text-xs text-text-muted mt-2">クリックで初期状態に戻る</p>
        </button>

        <div className="mb-4 border-b border-border-custom flex gap-4">
          {/* スマホ: 現場リサーチ | データ分析、PC: データ分析 | 現場リサーチ */}
          {isMobile ? (
            <>
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
            </>
          ) : (
            <>
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
            </>
          )}
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
                <TableView data={filteredData} miscExpenses={miscExpenses} />
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
            {!isMobile && (
              <Pagination
                totalItems={filteredData.length}
                itemsPerPage={itemsPerPage}
                currentPage={currentPage}
                onPageChange={setCurrentPage}
              />
            )}
            {isMobile && (
              <p className="text-sm text-text-muted py-2 mb-2">
                {currentData.length}件表示（{filteredData.length}件中）
              </p>
            )}
            <CardList data={currentData} miscExpenses={miscExpenses} />
            {isMobile && hasMoreMobile && (
              <div ref={loadMoreSentinelRef} className="h-4" aria-hidden="true" />
            )}
            {!isMobile && (
              <Pagination
                totalItems={filteredData.length}
                itemsPerPage={itemsPerPage}
                currentPage={currentPage}
                onPageChange={setCurrentPage}
              />
            )}
          </div>
        </div>
      </main>

      {/* モバイル: 固定下部メニュー */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-gray-800 border-t border-gray-700 shadow-lg">
        <button
          type="button"
          onClick={() => setBottomMenuOpen(true)}
          className="w-full py-4 px-4 font-bold flex items-center justify-center gap-2 text-gray-100 hover:bg-gray-700 transition-colors"
        >
          <span>▶</span>
          <span>🔍 フィルター・統計</span>
        </button>
      </div>

      {/* モバイル: 下部メニューから開くサイドバー（ボトムシート） */}
      {bottomMenuOpen && (
        <>
          <div
            role="button"
            tabIndex={0}
            aria-label="閉じる"
            className="md:hidden fixed inset-0 bg-black/50 z-50"
            onClick={() => setBottomMenuOpen(false)}
            onKeyDown={(e) => e.key === "Escape" && setBottomMenuOpen(false)}
          />
          <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 max-h-[85vh] overflow-y-auto bg-bg-sidebar border-t border-border-custom rounded-t-xl shadow-2xl animate-slide-up">
            <div className="sticky top-0 bg-bg-sidebar flex justify-between items-center p-4 border-b border-border-custom">
              <span className="font-bold text-accent">🔍 フィルター・統計</span>
              <button
                type="button"
                onClick={() => setBottomMenuOpen(false)}
                className="px-3 py-1 rounded border border-border-custom hover:bg-accent-light/20"
              >
                閉じる
              </button>
            </div>
            <div className="p-4">
              <Filters filters={filters} setFilters={setFilters} stats={stats} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default App;
