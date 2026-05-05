SELECT
  split(logline, ' ')[2] AS request_time,
  split(logline, ' ')[3] AS load_balancer,
  split(logline, ' ')[4] AS client_tuple,
  split(logline, ' ')[13] AS received_bytes,
  split(logline, ' ')[14] AS sent_bytes,
  try_cast(split(logline, ' ')[9] AS integer) AS elb_status_code,
  try_cast(split(logline, ' ')[10] AS integer) AS target_status_code
FROM alb_access_logs_raw
WHERE try_cast(split(logline, ' ')[9] AS integer) >= 500
ORDER BY request_time DESC
LIMIT 100;
