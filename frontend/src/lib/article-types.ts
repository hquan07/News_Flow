export interface ArticleFilters {
  source: string;
  category: string;
  dateFrom: string;
  dateTo: string;
}

export const EMPTY_ARTICLE_FILTERS: ArticleFilters = {
  source: "",
  category: "",
  dateFrom: "",
  dateTo: "",
};
