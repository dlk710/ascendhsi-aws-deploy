SELECT
  uri_stem,
  status,
  count(*) AS request_count
FROM cloudfront_access_logs
WHERE status >= 400
GROUP BY uri_stem, status
ORDER BY request_count DESC
LIMIT 50;
