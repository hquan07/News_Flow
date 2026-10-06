export interface ArticleFilters {
  author: string;
  source: string;
  category: string;
  dateFrom: string;
  dateTo: string;
  entity: string;
  keyword: string;
  sentiment: string;
}

export const EMPTY_ARTICLE_FILTERS: ArticleFilters = {
  author: "",
  source: "",
  category: "",
  dateFrom: "",
  dateTo: "",
  entity: "",
  keyword: "",
  sentiment: "",
};
