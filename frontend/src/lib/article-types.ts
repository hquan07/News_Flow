export interface ArticleFilters {
  source: string;
  category: string;
  dateFrom: string;
  dateTo: string;
  entity: string;
  keyword: string;
  sentiment: string;
}

export const EMPTY_ARTICLE_FILTERS: ArticleFilters = {
  source: "",
  category: "",
  dateFrom: "",
  dateTo: "",
  entity: "",
  keyword: "",
  sentiment: "",
};
