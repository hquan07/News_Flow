import os, sys
sys.path.append("/home/hquan07/News_Flow")
from dotenv import load_dotenv
load_dotenv()
from infrastructure.monitoring.telegram_alert import send_telegram_alert
import clickhouse_connect

client = clickhouse_connect.get_client(host="localhost", port=8123, username="default", password="")
volume_query = """
WITH hourly AS (
    SELECT toStartOfHour(publish_time) AS hour_slot, count() AS cnt 
    FROM newspulse.raw_articles 
    WHERE publish_time >= now() - INTERVAL 7 DAY GROUP BY hour_slot
), stats AS (
    SELECT avg(cnt) AS avg_cnt, stddevPop(cnt) AS std_cnt FROM hourly
) 
SELECT h.hour_slot, h.cnt AS article_count, toInt32(s.avg_cnt) AS avg_count 
FROM hourly h, stats s 
WHERE h.cnt > s.avg_cnt + 2.0 * s.std_cnt 
ORDER BY h.hour_slot DESC
"""
volume_results = client.query_df(volume_query)

if not volume_results.empty:
    vol_msg = "🌪 <b>BÃO TIN TỨC TRONG QUÁ KHỨ (HISTORICAL SPIKES)</b>:\n\n"
    for _, row in volume_results.iterrows():
        surge = round(row["article_count"] / max(row["avg_count"], 1), 1)
        time_str = row['hour_slot'].strftime('%H:%M %d/%m')
        article_count = row['article_count']
        avg_count = row['avg_count']
        vol_msg += f"- Khung giờ <b>{time_str}</b>: {article_count} tin (Tăng <b>{surge}x</b> so với TB {avg_count})\n"
    send_telegram_alert(vol_msg)
    print("Sent historical alerts!")
else:
    print("No historical alerts found.")
