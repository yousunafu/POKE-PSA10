/**
 * 鑑定費・手取り利益・利益率の計算ロジック
 * - 予想最大利益 10,000円以下: 非表示（鑑定費を引くと割に合わない）
 * - 10,001円〜29,999円: 鑑定費 3,000円（2〜3ヶ月プラン）
 * - 30,000円以上: 鑑定費 10,000円（約1ヶ月プラン）
 */

export const GRADE_FEE_STANDARD = 3000;
export const GRADE_FEE_EXPRESS = 10000;
export const MIN_PROFIT_TO_SHOW = 10001;
export const EXPRESS_THRESHOLD = 30000;

/**
 * 予想最大利益に応じた鑑定費を返す
 * @param {number} maxProfit - 予想最大利益（買取価格 - 仕入れ値）
 * @returns {number|null} 鑑定費。10,000円以下なら null（非表示対象）
 */
export function getGradingFee(maxProfit) {
  const p = Number(maxProfit) || 0;
  if (p < MIN_PROFIT_TO_SHOW) return null;
  if (p >= EXPRESS_THRESHOLD) return GRADE_FEE_EXPRESS;
  return GRADE_FEE_STANDARD;
}

/**
 * 手取り利益（予想最大利益 - 鑑定費）
 * @param {number} maxProfit
 * @param {number|null} gradingFee - getGradingFee の結果
 * @returns {number|null} 手取り利益。非表示対象なら null
 */
export function getNetProfit(maxProfit, gradingFee) {
  if (gradingFee == null) return null;
  return (Number(maxProfit) || 0) - gradingFee;
}

/**
 * 利益率 = 手取り利益 ÷ (仕入れ値 + 鑑定費) × 100
 * @param {number} netProfit - 手取り利益
 * @param {number} purchasePrice - 仕入れ値（素体の購入価格）
 * @param {number} gradingFee - 鑑定費
 * @returns {number} 利益率（%）
 */
export function getProfitRate(netProfit, purchasePrice, gradingFee) {
  const totalCost = (Number(purchasePrice) || 0) + (Number(gradingFee) || 0);
  if (totalCost <= 0) return 0;
  return ((Number(netProfit) || 0) / totalCost) * 100;
}

/**
 * 3,000円プラン（2ヶ月拘束）の月換算利益率
 * @param {number} profitRate - 計算上の利益率
 * @returns {number} 月換算利益率（概算）
 */
export function getMonthlyProfitRate(profitRate) {
  return (Number(profitRate) || 0) / 2;
}

/**
 * リスクリワード（鑑定失敗時の想定損失）
 * = 鑑定料 + 販売価格の10%（素体で売る時の販売サイト手数料想定）
 * @param {number} gradingFee - 鑑定費
 * @param {number} purchasePrice - 仕入れ値（販売価格）
 * @returns {number} リスクリワード
 */
export function getRiskReward(gradingFee, purchasePrice) {
  const fee = Number(gradingFee) || 0;
  const price = Number(purchasePrice) || 0;
  return Math.round(fee + price * 0.1);
}

/**
 * 1枚のカードに対する鑑定・利益の算出結果
 */
export function calcCardProfit(card) {
  const buyPrice = Number(card.buy_price) || 0;
  const sellPrice = Number(card.sell_price) || 0;
  const maxProfit = card.profit != null ? Number(card.profit) : buyPrice - sellPrice;

  const gradingFee = getGradingFee(maxProfit);
  if (gradingFee == null) return null;

  const netProfit = getNetProfit(maxProfit, gradingFee);
  const profitRate = getProfitRate(netProfit, sellPrice, gradingFee);
  const monthlyRate = gradingFee === GRADE_FEE_STANDARD
    ? getMonthlyProfitRate(profitRate)
    : null;
  const riskReward = getRiskReward(gradingFee, sellPrice);

  return {
    psa10Price: buyPrice,
    purchasePrice: sellPrice,
    gradingFee,
    maxProfit,
    netProfit,
    profitRate,
    monthlyRate,
    riskReward,
    isExpress: gradingFee === GRADE_FEE_EXPRESS,
  };
}
