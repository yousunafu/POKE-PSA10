import { useEffect } from "react";

export default function Pagination({
  totalItems,
  itemsPerPage,
  currentPage,
  onPageChange,
}) {
  const totalPages = Math.max(1, Math.ceil(totalItems / itemsPerPage));

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [currentPage]);

  if (totalPages <= 1) return null;

  const handlePageChange = (newPage) => {
    const p = Math.max(1, Math.min(totalPages, Number(newPage)));
    if (p !== currentPage) onPageChange(p);
  };

  const start = (currentPage - 1) * itemsPerPage + 1;
  const end = Math.min(currentPage * itemsPerPage, totalItems);

  return (
    <div className="py-4 space-y-3">
      <div className="flex justify-center items-center gap-2">
        <span className="text-sm text-text-muted">ページ指定:</span>
        <input
          type="number"
          min={1}
          max={totalPages}
          value={currentPage}
          onChange={(e) => {
            const val = parseInt(e.target.value, 10);
            if (!isNaN(val)) handlePageChange(val);
          }}
          className="w-16 border border-border-custom rounded px-2 py-1 text-center text-sm"
        />
      </div>
      <div className="flex justify-center items-center gap-2 text-sm flex-wrap">
        <button
          type="button"
          onClick={() => handlePageChange(Math.max(1, currentPage - 10))}
          disabled={currentPage <= 10}
          className="px-3 py-2 bg-white border border-border-custom rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          ◀◀ 10前
        </button>
        <button
          type="button"
          onClick={() => handlePageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className="px-3 py-2 bg-white border border-border-custom rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          ◀ 前へ
        </button>
        <span className="px-2 text-text-muted whitespace-nowrap">
          ページ {currentPage} / {totalPages}（{totalItems}件中 {start}–{end}件を表示）
        </span>
        <button
          type="button"
          onClick={() => handlePageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="px-3 py-2 bg-white border border-border-custom rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          次へ ▶
        </button>
        <button
          type="button"
          onClick={() =>
            handlePageChange(Math.min(totalPages, currentPage + 10))
          }
          disabled={currentPage >= totalPages - 9}
          className="px-3 py-2 bg-white border border-border-custom rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          10後 ▶▶
        </button>
      </div>
    </div>
  );
}
