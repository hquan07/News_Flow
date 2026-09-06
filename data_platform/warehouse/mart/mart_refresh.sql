\echo '=== NewsPulse Mart Refresh Start ==='
\echo ''

-- 1. Daily overview (no dependencies)
\echo '>> Refreshing mart_daily_overview...'
\i mart_daily_overview.sql
\echo '   Done.'

-- 2. Hourly distribution (no dependencies)
\echo '>> Refreshing mart_hourly_distribution...'
\i mart_hourly_distribution.sql
\echo '   Done.'

-- 3. Trending keywords (no dependencies)
\echo '>> Refreshing mart_trending_keywords...'
\i mart_trending_keywords.sql
\echo '   Done.'

-- 4. Source comparison (depends on bridge_article_keyword)
\echo '>> Refreshing mart_source_comparison...'
\i mart_source_comparison.sql
\echo '   Done.'

-- 5. Entity stats (depends on bridge_article_entity)
\echo '>> Refreshing mart_entity_stats...'
\i mart_entity_stats.sql
\echo '   Done.'

\echo ''
\echo '=== NewsPulse Mart Refresh Complete ==='